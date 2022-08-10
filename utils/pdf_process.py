import os
from uuid import uuid4
import cv2
import fitz
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from pytesseract import image_to_pdf_or_hocr

from .config import temp_folder


def check_drm_and_language(doc, ):
    """ Get page-wise status of DRM protection.
    Args:
        doc (fitz.Document): PDF Document object
    Returns:
        dict: Format- {page_no : True/False}
              True = DRM Protected
              False = Not DRM Protected
    """
    page_details = {}
    english_pages = 0
    for page in doc:
        ascii_count = 0
        total_count = 0
        text = page.get_text("text")
        total_count = len(text)
        page_details[page.number] = {}
        if total_count != 0:
            for c in text:
                if c.isascii():
                    ascii_count += 1
            percentage_ascii = ascii_count / total_count
            if percentage_ascii > 0.2:
                page_details[page.number]["drm_status"] = False
            else:
                page_details[page.number]["drm_status"] = True
        else:
            page_details[page.number]["drm_status"] = False

    return page_details


def check_scanned(doc, page_details):
    scanned_count, digital_count = 0, 0
    for page in doc:
        text = page.getText()
        if len(text) > 100:
            page_details[page.number]["is_scanned"] = False
            digital_count += 1
        else:
            page_details[page.number]["is_scanned"] = True
            page_details[page.number]["drm_status"] = False
            scanned_count += 1
    if scanned_count >= digital_count:
        return page_details, True
    return page_details, False


def check_dpi(doc, page_details):
    gt_250 = 0
    faulty_page_nos = []
    scanned_pages = 0
    for page in doc:
        if page_details[page.number]["is_scanned"]:
            img = page.getImageList()
            if len(img) >= 1:
                pix = fitz.Pixmap(doc, img[0][0])
                if pix.colorspace.name == "DeviceCMYK":
                    pix = page.getPixmap(matrix=fitz.Matrix(2, 2))
            else:
                pix = page.getPixmap(matrix=fitz.Matrix(2, 2))
            rect = pix.irect
            prect = page.rect
            dpi = int(72 * rect[2] / prect[2])
            scanned_pages += 1
            if dpi >= 250:
                gt_250 += 1
            else:
                faulty_page_nos.append(page.number + 1)
    if scanned_pages != 0:
        dpi_pass_percentage = gt_250 / scanned_pages
    else:
        dpi_pass_percentage = 100
    if dpi_pass_percentage > 50:
        return True, faulty_page_nos
    return False, faulty_page_nos


def flags_decomposer(flags):
    """Make font flags human readable."""
    l = []
    if flags & 2 ** 0:
        l.append("superscript")
    if flags & 2 ** 1:
        l.append("italic")
    if flags & 2 ** 2:
        l.append("serifed")
    else:
        l.append("sans")
    if flags & 2 ** 3:
        l.append("monospaced")
    else:
        l.append("proportional")
    if flags & 2 ** 4:
        l.append("bold")
    return l


def page_to_df(page):
    blocks = page.getText("dict")["blocks"]
    data, block_data = [], []
    for block_num, block in enumerate(blocks):
        bbox = np.array(block["bbox"]).astype("int")
        block_data.append(bbox)
        if "image" in block.keys():
            continue
        for line_num, line in enumerate(block["lines"]):
            for span_num, span in enumerate(line["spans"]):
                bbox = np.array(span["bbox"]).astype("int")
                x1, y1, x2, y2 = bbox
                text = span["text"]
                size, style = int(span["size"]), flags_decomposer(
                    int(span["flags"]))
                color = fitz.sRGB_to_pdf(span["color"])
                font = span["font"]
                rect = fitz.Rect(bbox)
                if rect not in page.rect or text == " ":
                    continue
                data.append(
                    (
                        x1,
                        y1,
                        x2,
                        y2,
                        text,
                        size,
                        style,
                        color,
                        font,
                        block_num,
                        line_num,
                        span_num,
                        rect,
                    )
                )
    df = pd.DataFrame(
        columns=[
            "x1",
            "y1",
            "x2",
            "y2",
            "text",
            "size",
            "style",
            "color",
            "font",
            "block_num",
            "line_num",
            "span_num",
            "rect",
        ],
        data=data,
    )
    return df


def check_overlap_area(bbox, rect, threshold):
    return fitz.Rect(bbox).intersect(rect).getRectArea() > threshold * min(
        fitz.Rect(bbox).getRectArea(), rect.getRectArea()
    )


def page_to_image(page, scale=1):
    pixmap = page.getPixmap(matrix=fitz.Matrix(scale, scale))
    # pixmap.writeImage("temp.png")
    nparr = np.fromstring(pixmap.getPNGData(), np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
    # img = cv2.imread("temp.png")
    x_dpi = int(72 * pixmap.irect[2] / page.rect[2])
    y_dpi = int(72 * pixmap.irect[3] / page.rect[3])
    dpi = min(x_dpi, y_dpi)
    return img, dpi


def get_scanned_page_as_df(img, dpi, scale):
    # img, dpi = self.get_page_as_image(page_num, scale)
    temp_file = os.path.join(temp_folder, f"{uuid4()}.png")
    cv2.imwrite(temp_file, img)
    ocr_config = f"--oem 1 --psm 1 hocr_font_info=1 --dpi {dpi}"
    hocr = image_to_pdf_or_hocr(
        temp_file, lang="eng", config=ocr_config, extension="hocr"
    )

    soup = BeautifulSoup(hocr, features="lxml")
    data = []
    for block_num, block in enumerate(soup.find_all("div", {"class": "ocr_carea"})):
        for par_num, par in enumerate(block.find_all("p", {"class": "ocr_par"})):
            lines = par.find_all("span", recursive=False)
            for line_num, line in enumerate(lines):
                words = line.find_all("span")
                for word_num, word in enumerate(words):
                    text = word.string
                    if text in [" "]:
                        continue
                    txt = text
                    details = word["title"].split(";")
                    for prop in details:
                        prop = [d for d in prop.split(" ") if d]
                        if prop[0] == "bbox":
                            x1 = int(prop[1]) / scale
                            y1 = int(prop[2]) / scale
                            x2 = int(prop[3]) / scale
                            y2 = int(prop[4]) / scale
                            size = y2 - y1
                        elif prop[0] == "x_wconf":
                            conf = int(prop[1])
                        elif prop[0] == "x_fsize":
                            size = int(prop[1])
                    block_num = block_num
                    par_num = par_num
                    line_num = line_num
                    word_num = word_num
                    data.append(
                        (
                            x1,
                            y1,
                            x2,
                            y2,
                            txt,
                            size,
                            "normal",
                            np.nan,
                            np.nan,
                            block_num,
                            line_num,
                            word_num,
                            fitz.Rect([x1, y1, x2, y2]),
                        )
                    )
    df = pd.DataFrame(
        columns=[
            "x1",
            "y1",
            "x2",
            "y2",
            "text",
            "size",
            "style",
            "color",
            "font",
            "block_num",
            "line_num",
            "span_num",
            "rect",
        ],
        data=data,
    )
    return df


def create_page(doc, page):
    page_rect = page.MediaBox
    # del page
    # temp_page = gen.doc.newPage(pno = -1, width = page_rect.x1 - page_rect.x0, height =  page_rect.y1 - page_rect.y0)
    temp_page = doc.newPage(
        pno=-1,
        width=page_rect.width,
        height=page_rect.height,
    )
    return temp_page

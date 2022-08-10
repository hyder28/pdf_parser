import os
from uuid import uuid4
from pathlib import Path
import cv2
import fitz
import numpy as np
import pandas as pd
from .pdf_process import get_scanned_page_as_df, page_to_image, page_to_df, create_page
import logging


class TextExtractor:
    def __init__(self, is_scanned):
        self.path = ""
        self.doc = None
        self.is_scanned = is_scanned
        self.data_df = pd.DataFrame()

    def __get_font_style(self, flags):
        ftype = ""
        if flags & 2 ** 1:
            ftype += "italic"
        if flags & 2 ** 4:
            ftype += "bold"
        if ftype == "":
            ftype = "normal"
        return ftype

    def __get_font_name(self, font, fonts):
        for f in fonts.keys():
            if font.lower() == f.lower():
                return f

    def __is_line_present(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=gray.shape[1] // 10,
            minLineLength=gray.shape[1] // 15,
        )
        # return edges
        if lines is None:
            return False
        else:
            return True

    def get_rawpage_as_df(self, page):
        """
        Generates a dataframe of PDF page containing data to the level of each letter
        """
        try:
            blocks = page.getTextPage().extractRAWDICT()["blocks"]
            data = []
            for block_num, block in enumerate(blocks):
                if "image" in block.keys():
                    continue
                for line_num, line in enumerate(block["lines"]):
                    for span_num, span in enumerate(line["spans"]):
                        for _, char in enumerate(span["chars"]):
                            x1, y1 = int(char["bbox"][0]), int(char["bbox"][1])
                            x2, y2 = int(char["bbox"][2]), int(char["bbox"][3])
                            text = char["c"]
                            size, style = int(span["size"]), self.__get_font_style(
                                int(span["flags"])
                            )
                            color = span["color"]
                            font = span["font"]
                            rect = fitz.Rect(x1, y1, x2, y2)
                            # if rect not in page.rect or text == " ":
                            #     continue
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
        except Exception as e:
            logging.error(f"> error in extracting raw text for {self.file_name}, {self.page_num}.")

            return pd.DataFrame()

    def __print_on_page(self, temp_page, fonts, row):
        try:
            return temp_page.insert_text(
                fitz.Point(row["x1"], row["y2"]),
                row["text"],
                fontsize=row["size"],
                # fontname=row["font"]
                # if (self._TextExtractor__get_font_name(row["font"], fonts)) != None
                # else "helv",
                # fontfile=fonts[self._TextExtractor__get_font_name(
                #     row["font"], fonts)],
                fontname="helv",
                fontfile=None,
                color=None,
                overlay=True,
            )
        except Exception as e:
            logging.error(f"> unable to write on new page for {self.file_name}, {self.page_num}")

    def get_stripped_page(self, page):
        """
        Strips the PDF page of all the Lines and Figures preserving only copyable the text.
        """

        try:
            temp_page = create_page(self.doc, page)

            fonts = {}

            page_df = self.get_rawpage_as_df(page)

            page_df.apply(
                lambda row: self.__print_on_page(temp_page, fonts, row),
                axis=1,
            )
            img, _ = page_to_image(self.doc[self.doc.pageCount - 1], 4)
            # page_num = page.number
            self.doc.deletePage(self.doc.pageCount - 1)
        except Exception as e:
            logging.error(
                "> error in extracting stripped page for {self.file_name}, {self.page_num}.\nReturning original page image by default.")

            img, _ = page_to_image(page, 4)
        return img

    def get_blocks_bbox_by_cv(self, page):
        """ Generates bounding boxes of text blocks using OpenCV.
        It first generates stripped page, i.e., removes everything (lines, images, objects,etc.)
        from the page except the text.
        Args:
            page (fitz.Page): Document page object is directly passed.
        Returns:
            [pd.DataFrame]: DataFrame containing bbox and label of the extracted text.
        """
        try:
            blocks_data = []
            blocks_columns = [
                "x1",
                "y1",
                "x2",
                "y2",
                "block_num",
                "rect",
                "label",
            ]
            block_num = 0
            if self.is_scanned:
                scale = 4
                img, dpi = page_to_image(page, scale)
                self.page_df = get_scanned_page_as_df(img, dpi, scale)
            else:
                scale = 4
                img = self.get_stripped_page(page)
                self.page_df = page_to_df(page)
                self.page_df["style"] = self.page_df["style"].apply(
                    lambda item: "bold"
                    if "bold" in item
                    else ("italic" if "italic" in item else "normal")
                )
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            kernel = np.ones((5, 5), np.uint8)
            gray_img = 255 - gray_img
            img_dilation = cv2.morphologyEx(
                gray_img, cv2.MORPH_CLOSE, kernel, iterations=7)
            _, img_dilation = cv2.threshold(
                img_dilation, 0, 255, cv2.THRESH_BINARY)
            # Generate Contours
            contours, _ = cv2.findContours(
                img_dilation, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
            )
            # img, _ = page_to_image(page)
            for cnt in contours:
                # Generating bounding boxes for contours
                x, y, w, h = cv2.boundingRect(cnt)
                x /= scale
                y /= scale
                w /= scale
                h /= scale
                if w > 2 and h > 2:
                    rect = fitz.Rect(
                        [x, y, (x + w), (y + h)]
                    )  # All the coordinates are divided by 4 because the image was scaled 4 times while reading
                    block_df = self.page_df[
                        self.page_df["rect"].apply(rect.intersects)
                    ].copy()
                    label = "text"
                    if block_df.empty:
                        label = "figure"
                    img = cv2.rectangle(
                        img, (int(x), int(y)), (int(x + w), int(y + h)), (255, 0, 0), 2)
                    blocks_data.append(
                        [
                            x,
                            y,
                            (x + w),
                            (y + h),
                            block_num,
                            rect,
                            label,
                        ]
                    )
                block_num += 1
            blocks_df = pd.DataFrame(data=blocks_data, columns=blocks_columns)
            # cv2.imwrite("check.png", img)
            if blocks_df.empty:
                raise ValueError(f"No text blocks detected.")
            return blocks_df
        except ValueError as e:
            logging.error(f"> no text blocks detected for {self.file_name}, {self.page_num}")
            return pd.DataFrame()
        except Exception as e:
            logging.error(f"> error in generating block bboxes for {self.file_name}, {self.page_num}")

            return pd.DataFrame()

    # def __merging_bboxes(self, index, row):
    def merge_overlapping_bbox(self, blocks_df):
        try:
            blocks_columns = [
                "x1",
                "y1",
                "x2",
                "y2",
                "block_num",
                "rect",
                "label",
            ]
            blocks_df["to_delete"] = 0
            new_block_data = {}
            for index, row in blocks_df.iterrows():
                if row["to_delete"] == 0:
                    temp_df = blocks_df[blocks_df["rect"].apply(
                        row["rect"].intersects)]
                    if len(temp_df) > 1:
                        new_row = row.copy()
                        blocks_df.at[index, "to_delete"] = 1
                        new_row["label"] = temp_df["label"].values[0]
                        new_row["x1"] = new_row["rect"].x0
                        new_row["y1"] = new_row["rect"].y0
                        new_row["x2"] = new_row["rect"].x1
                        new_row["y2"] = new_row["rect"].y1
                        new_block_data[new_row["rect"]] = new_row.to_list()
            t_df = pd.DataFrame(
                data=list(new_block_data.values()), columns=blocks_columns + ["to_delete"]
            )
            blocks_df = blocks_df.append(t_df)
            blocks_df.reset_index(drop=True, inplace=True)
            blocks_df.drop(
                blocks_df[blocks_df["to_delete"] == 1].index, inplace=True)
            blocks_df.reset_index(drop=True, inplace=True)
            return blocks_df
        except Exception as e:
            logging.error(f"> error in merging bboxes for {self.file_name}, {self.page_num}")
            return pd.DataFrame()

    def get_page_blocks_with_text(self, page):
        try:
            new_blocks_columns = [
                "sx1",
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
                "pdf_rect",
                "cv_rect",
                "label",
            ]
            block_data = {}
            block_num = 0
            blocks_df = self.get_blocks_bbox_by_cv(page)
            blocks_df = self.merge_overlapping_bbox(blocks_df)
            self.page_df["is_used"] = False
            for _, out_row in blocks_df.iterrows():
                rect = out_row["rect"]
                temp_df = self.page_df[(self.page_df["rect"].apply(rect.intersects)) &
                                       ~(self.page_df["is_used"])].copy()
                self.page_df.at[(self.page_df["rect"].apply(
                    rect.intersects)), "is_used"] = True
                temp_df["label"] = out_row["label"]
                temp_df["text"] = temp_df["text"].apply(str)
                temp_df.reset_index(inplace=True)
                if not temp_df.empty:
                    prev_row = pd.Series()
                    for index, row in temp_df.iterrows():
                        if prev_row.empty:
                            if (
                                    row["style"] != "normal"
                                    and not self.is_scanned
                            ):  # if font style is not normal
                                temp_df.at[index, "label"] = "title"
                                prev_row = row
                            else:
                                break
                        elif not prev_row.empty:
                            txt = row["text"]
                            if len(txt.split()) > 1:
                                first = txt.split()[0]
                                rest = " ".join(txt.split()[1:])
                                # FIXING FULLSTOP CARRYOVER
                                if first == ".":
                                    temp_df.at[index - 1, "text"] += first
                                    temp_df.at[index, "text"] = rest
                                # FIXIND SUPERSCRIPT CARRYOVER
                                elif row["style"] != "normal" and row["text"].isdigit():
                                    temp_df.at[index - 1,
                                               "text"] += " [" + first + "]"
                                    temp_df.at[index, "text"] = rest
                            if (
                                    row["style"] == prev_row["style"]
                                    and (row["font"] == prev_row["font"])
                                    and (row["size"] == prev_row["size"])
                            ):  # Check if the header is title block is overflowing to the next span
                                temp_df.at[index, "label"] = "title"
                                prev_row = row
                            else:
                                break
                    for label in temp_df["label"].unique():
                        try:
                            label_df = temp_df[temp_df["label"] == label]
                            # Get coordinate of first word to correctly identify indentation #
                            sx1 = label_df.sort_values("y2").iloc[0]["x1"]
                            x1 = label_df["x1"].min()
                            y1 = label_df["y1"].min()
                            x2 = label_df["x2"].max()
                            y2 = label_df["y2"].max()
                            text = " ".join(label_df["text"])
                            # Get font attributes of the first span
                            first_row = label_df.reset_index().iloc[0]
                            size = first_row["size"]
                            font = first_row["font"]
                            style = first_row["style"]
                            color = first_row["color"]
                            pdf_rect = fitz.Rect([x1, y1, x2, y2])
                            if pdf_rect not in block_data.keys():
                                block_data[pdf_rect] = [
                                    sx1,
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
                                    pdf_rect,
                                    pdf_rect,
                                    label,
                                ]
                                block_num += 1
                            else:
                                block_data[pdf_rect][12].includeRect(
                                    rect
                                )  # If text block is repeated, merge them.
                        except Exception as e:
                            logging.error("> error in generating page dataframe")

            data_df = pd.DataFrame(
                data=list(block_data.values()), columns=new_blocks_columns
            )
            return data_df
        except Exception as e:
            logging.error(f"> error in generating text blocks for {self.file_name}, {self.page_num}")

            return pd.DataFrame()

    def read_pdf_to_df(self, path, page, is_scanned):
        try:
            self.is_scanned = is_scanned
            self.file_name = Path(path).name
            self.page_num = page.number
            logging.info(f"> begin text extraction for {self.file_name}, {page.number}")
            self.doc = fitz.open(path)
            data_df = self.get_page_blocks_with_text(page)
            data_df.reset_index(drop=True, inplace=True)
            self.data_df = data_df
        except Exception as e:
            logging.error(f"> error in extracting text from {self.file_name}, {self.page_num}")

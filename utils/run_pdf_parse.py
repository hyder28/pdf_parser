import os
import warnings

from datetime import datetime

import fitz  # PyMuPDF
import pandas as pd

from utils.pdf_utils import check_drm_and_language, check_scanned, check_dpi
from utils.page_processor import PageProcessor
from utils.pc_relation_gen import PCRelationGen

warnings.filterwarnings("ignore")


def get_pdf_extraction(pdf_fpath, pdf_fname):
    doc = fitz.open(pdf_fpath)
    page_details = check_drm_and_language(doc)
    page_details, is_scanned = check_scanned(doc, page_details)
    is_dpi_valid, faulty_page_nos = check_dpi(doc, page_details)

    if is_dpi_valid == False:
        print(f"The pdf DPI is less than 250 for pages {faulty_page_nos} of {pdf_fname}")

    print(f"Processing PDF...")
    page_proc = PageProcessor(is_scanned=is_scanned)
    pdf_data = pd.DataFrame()
    pc_relation_gen = PCRelationGen()

    for page in doc:
        if page_details[page.number]["drm_status"] == False:
            page_data = page_proc.extract_data_from_page(pdf_fpath, page,
                                                         page_details[page.number]["is_scanned"])

        if page_details[page.number]["drm_status"] == True or page_data is None:
            print(f"> {page.number} is DRM Protected")
            page_data_columns = ['sx1', 'x1', 'y1', 'x2', 'y2', 'text', 'size', 'style', 'color', 'font',
                                 'block_num', 'pdf_rect', 'cv_rect', 'label', 'page_num', 'intersection',
                                 'multicolumn', 'col_no', 'quant_y', 'cv_rect_width', 'norm_rect',
                                 'to_delete', 'centroid_x', 'centroid_y']
            drm_protected_data = [0, 0, 0, 0, 0, "Page is DRM Protected", 0, "None", 0, "None", 0, [], [], "None",
                                  0,
                                  0, 0, 0, 0, [], [], 0, 0, 0]

            page_data = pd.DataFrame(data=[drm_protected_data], columns=page_data_columns)

        page_data["page_no"] = page.number + 1
        pdf_data = pdf_data.append(page_data)

    # Create Parent - Child relationships
    print("Creating parent-child relations...")
    if pdf_data.empty:
        raise ValueError("No data extracted from pdfs")

    pdf_data.reset_index(drop=True, inplace=True)
    pdf_data["merge_next"] = False
    pdf_data["text"] = pdf_data["text"].apply(lambda txt: txt.strip())
    merge_next_index = ~((pdf_data["text"].str.endswith(".")) |
                         (pdf_data["text"].str.endswith(":")) |
                         (pdf_data["text"].str.endswith(";")) |
                         (pdf_data["text"].str.endswith("?")) |
                         (pdf_data["text"].str.endswith("”")) |
                         (pdf_data["text"].str.endswith("\"")))
    pdf_data.at[merge_next_index, "merge_next"] = True
    pdf_data["text_len"] = pdf_data["text"].apply(len)
    wm_df = pdf_data.at[pdf_data[(pdf_data["label"] == "watermark") &
                                 (pdf_data["text_len"] >= 50)].index, "label"] = "text"
    pdf_data.at[pdf_data["label"] == "title", "merge_next"] = False
    wm_indices = pdf_data["label"] == "watermark"
    pdf_data = pdf_data[~(wm_indices)].copy()
    pdf_data["to_delete"] = False
    prev_row = pd.Series()
    prev_ind = -1
    for ind, row in pdf_data.iterrows():
        if row["label"] == "title":
            prev_row = pd.Series()
            prev_ind = -1
            continue
        if not prev_row.empty:
            if prev_row["merge_next"] == True and len(row["text"]) > 0:
                if row["text"][0].islower() and row["text"][0].isalnum():
                    text = pdf_data.loc[prev_ind]["text"]
                    pdf_data.at[ind, "to_delete"] = True
                    pdf_data.at[prev_ind, "text"] = text + " " + row["text"]
                    if prev_row["page_no"] == row["page_no"]:
                        x1 = min(row["x1"], prev_row["x1"])
                        y1 = min(row["y1"], prev_row["y1"])
                        x2 = max(row["x2"], prev_row["x2"])
                        y2 = max(row["y2"], prev_row["y2"])
                        pdf_data.at[prev_ind, "x1"] = x1
                        pdf_data.at[prev_ind, "y1"] = y1
                        pdf_data.at[prev_ind, "x2"] = x2
                        pdf_data.at[prev_ind, "y2"] = y2
                    if not row["merge_next"]:
                        prev_row = row
                        prev_ind = ind
                else:
                    prev_row = row
                    prev_ind = ind
            else:
                prev_row = row
                prev_ind = ind
        else:
            prev_row = row
            prev_ind = ind
    pdf_data.drop(pdf_data[pdf_data["to_delete"] == True].index, inplace=True)
    pdf_data.reset_index(drop=True, inplace=True)

    df = pc_relation_gen.generate_relationship(pdf_data, pdf_fname)

    return df

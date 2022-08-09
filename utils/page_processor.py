from pathlib import Path
import numpy as np
import pandas as pd
import fitz
from utils.text_extractor import TextExtractor
from utils.pdf_utils import page_to_df, check_overlap_area, page_to_image, get_scanned_page_as_df
import logging


class PageProcessor:
    def __init__(self, is_scanned=False):
        # self.page = page
        self.is_scanned = is_scanned
        self.txt_extractor = TextExtractor(is_scanned)
        self.group_no = 0

    def __get_rect_width(self, rect):
        return rect.width

    def __get_centroid_coord(self, coord1, coord2):
        return (coord1 + coord2) / 2

    def __create_coord_groups_helper(self, diff, max_diff):
        """
        Helper function to vectorize __create_coord_groups function
        """
        if diff > max_diff:
            self.group_no += 1
        return self.group_no

    def __create_coord_groups(self, col, max_diff):
        """
        Function to group the data by coordinates hence creating either column numbers or line numbers
        """
        col = col.copy()
        # prev_item = -1
        self.group_no = 0
        ret_col = pd.Series()
        col.sort_values(ascending=True, inplace=True)
        new_col = col.copy()
        new_col = new_col.shift(1)
        new_col = col - new_col
        ret_col = new_col.apply(
            lambda diff: self.__create_coord_groups_helper(diff, max_diff))
        return ret_col

    def __adjust_df_format(self, df):
        """ Arrange dataframe column into format required for processing
        Required Columns: ["sx1", "x1", "y1", "x2", "y2",
                            "text", "size", "style", "color",
                            "font", "block_num", "pdf_rect", "cv_rect",
                            "label"]
        Args:
            df (pd.DataFrame): Dataframe whose format needs to be changed.
        """
        df["sx1"] = df["cv_rect"].apply(lambda rect: rect.x0)
        df["x1"] = df["cv_rect"].apply(lambda rect: rect.x0)
        df["x2"] = df["cv_rect"].apply(lambda rect: rect.x1)
        df["y1"] = df["cv_rect"].apply(lambda rect: rect.y0)
        df["y2"] = df["cv_rect"].apply(lambda rect: rect.y1)
        df["pdf_rect"] = df["cv_rect"]
        df["size"] = None
        df["style"] = None
        df["color"] = None
        df["font"] = None
        df["block_num"] = None
        df["line_num"] = None
        df["span_num"] = None
        return df

    def remove_border_elements(self, page, data_df):
        """ Creating a border of 10 % of width and height on all 4 sides.
        """
        try:
            top_thresh = page.MediaBox.height * 0.045
            left_thresh = page.MediaBox.width * 0.05
            bottom_thresh = page.MediaBox.height * 0.94
            right_thresh = page.MediaBox.width * 0.91
            clean_data_df = data_df[data_df["x2"] > left_thresh].copy()
            clean_data_df = clean_data_df[clean_data_df["y2"] > top_thresh].copy(
            )
            clean_data_df = clean_data_df[clean_data_df["x1"] < right_thresh].copy(
            )
            clean_data_df = clean_data_df[clean_data_df["y1"]
                                          < bottom_thresh].copy()
            return clean_data_df
        except Exception as e:
            logging.error(f"> error in removing border elements for {self.file_name}, {page.number}")
            return data_df

    def add_pagebreak(self, data_df):
        """ This function is used to create pagebreaks in cases where the
            page contains both single column and multi-column data.
        Args:
            data_df (pd.DataFrame): Merged dataframe with both text and table data
        Returns:
            pd.DataFrame: Returns dataframe with an additional column "multicolumn"
                          which divides the page into parts (pagebreaks).
        """
        try:
            for index, row in data_df.iterrows():
                if row["label"] == "table_image" or row["label"] == "table_html":
                    continue
                y1 = row["y1"]
                y2 = row["y2"]
                # CHECKING FOR INTERSECTIONS ALONG Y AXIS
                newdf = data_df[
                    data_df.apply(lambda x: (
                            x["y1"] <= y2 and x["y2"] >= y1), axis=1)
                ]
                if len(newdf.index) > 1:
                    data_df.loc[index, "intersection"] = 1
                cur = 0
                segment = 0
                data_df.sort_values(by=["y1"], ascending=[True], inplace=True)
                for index1, row1 in data_df.iterrows():
                    if row1["label"] == "table_image" or row1["label"] == "table_html":
                        data_df.loc[index1, "multicolumn"] = segment
                        continue
                    if row1["intersection"] != cur:
                        segment += 1
                        cur = row1["intersection"]
                        data_df.loc[index1, "multicolumn"] = segment
                    else:
                        data_df.loc[index1, "multicolumn"] = segment
            # self.data_df=df
            return data_df
        except Exception as e:
            logging.error(f"> error in adding pagebreaks for {self.file_name}, {self.page_num}")

            data_df.loc[index1, "multicolumn"] = 1
            return data_df

    def normalize_block_width(self, part_df):
        """ Changes the width of detected blocks to the average width in the dataframe.
        Args:
            part_df (pd.DataFrame): Part of the page dataframe after creating the pagebreaks
        Returns:
            [pd.DataFrame]:
        """
        try:
            part_df["col_no"] = self.__create_coord_groups(part_df["x1"], 50)
            part_df["quant_y"] = self.__create_coord_groups(part_df["y1"], 10)
            part_df["cv_rect_width"] = part_df["cv_rect"].apply(
                self.__get_rect_width)
            part_df.sort_values(by="col_no", ascending=True, inplace=True)
            part_df["norm_rect"] = np.nan
            part_df["norm_rect"] = part_df["norm_rect"].astype("object")
            for index, x in part_df["col_no"].iteritems():
                max_width = part_df[
                    (part_df["col_no"] == x)
                    & (part_df["label"] != "figure")
                    & (part_df["label"] != "table")
                    ]["cv_rect_width"].mean()
                x1, y1, x2, y2 = part_df.loc[index]["cv_rect"]
                if not np.isnan(max_width):
                    x2 = part_df.at[index, "x1"] + max_width
                part_df.at[index, "norm_rect"] = fitz.Rect(x1, y1, x2, y2)
            return part_df
        except Exception as e:
            logging.error(f"> error in block normalisation for {self.file_name}, {self.page_num}")

            return part_df

    def merge_normalized_rect(self, part_df, page_df):
        try:
            new_data = {}
            if self.is_scanned:
                unique_styles = part_df.groupby(["size"])
            else:
                unique_styles = part_df.groupby(["size", "style", "font"])
            part_df["to_delete"] = 0
            styles_dfs = [unique_styles.get_group(
                x) for x in unique_styles.groups]
            for groupby_styles_df in styles_dfs:
                for index, row in groupby_styles_df.iterrows():
                    if row["label"] == "table" or row["label"] == "table_image" or row["label"] == "table_html":
                        continue
                    # temp_df = groupby_styles_df[groupby_styles_df["norm_rect"].apply(
                    #     lambda rect: check_overlap_area(list(row["norm_rect"]), rect, 0.8))]
                    temp_df = groupby_styles_df[(
                                                    groupby_styles_df["norm_rect"].apply(
                                                        row["norm_rect"].intersects)) &
                                                (groupby_styles_df["label"] != "table") &
                                                (groupby_styles_df["label"] != "table_image") &
                                                (groupby_styles_df["label"] != "table_html")
                                                ]
                    if len(temp_df) > 1:
                        new_row = row.copy()
                        new_row["x1"] = temp_df["x1"].min()
                        new_row["y1"] = temp_df["y1"].min()
                        new_row["x2"] = temp_df["x2"].max()
                        new_row["y2"] = temp_df["y2"].max()
                        for i, row1 in temp_df.iterrows():
                            new_row["norm_rect"].includeRect(row1["norm_rect"])
                            part_df.at[i, "to_delete"] = 1
                        temp_df = page_df[
                            page_df["rect"].apply(
                                new_row["norm_rect"].intersects)
                        ].copy()
                        text = " ".join(temp_df["text"])
                        new_row["text"] = text
                        new_row["to_delete"] = 0
                        new_data[new_row["norm_rect"]] = new_row.to_list()
            t_df = pd.DataFrame(data=list(new_data.values()),
                                columns=part_df.columns)
            part_df = part_df.append(t_df)
            part_df.reset_index(drop=True, inplace=True)
            part_df.drop(part_df[part_df["to_delete"]
                                 == 1].index, inplace=True)
            part_df.reset_index(drop=True, inplace=True)
            return part_df
        except Exception as e:
            logging.error(f"> error in merging normalised boxes for {self.file_name}, {self.page_num}")

    def sort_in_reading_order(self, part_df):
        part_df["centroid_x"] = part_df["pdf_rect"].apply(
            lambda rect: self.__get_centroid_coord(rect.x0, rect.x1)
        )
        part_df["col_no"] = self.__create_coord_groups(part_df["x1"], 100)
        part_df["centroid_y"] = part_df["pdf_rect"].apply(
            lambda rect: self.__get_centroid_coord(rect.y0, rect.y1)
        )
        part_df.sort_values(
            by=["col_no", "centroid_y", "x1"],
            ascending=[True, True, True],
            inplace=True,
        )
        part_df.reset_index(drop=True, inplace=True)
        return part_df

    def extract_data_from_page(self, pdf_path, page, is_scanned):
        """ This is the main function of the PageProcessor class. It reads the page
            in given to it and returns it as a DataFrame arranged in reading order.
        Args:
            pdf_path (str): Path to pdf required for table extraction
            page (fitz.Page): Fitz Page class required to extract data from the page.
        Returns:
            [pd.DataFrame]: Returns the dataframe of the page in reading order
        """
        try:
            self.is_scanned = is_scanned
            self.file_name = Path(pdf_path).name
            self.page_num = page.number
            # text_thread = threading.Thread(target=self.txt_extractor.read_pdf_to_df,
            #                                args=(pdf_path, page))
            # table_thread = threading.Thread(target=self.table_extractor.get_table_data,
            #                                 args=(pdf_path, page))
            # text_thread.start()
            # table_thread.start()
            # # Wait for threads to finish execution
            # text_thread.join()
            # table_thread.join()
            self.txt_extractor.read_pdf_to_df(pdf_path, page, is_scanned)

            text_df = self.txt_extractor.data_df
            logging.info(f"> completed text extraction for {self.file_name}, {page.number}")
            data_df = text_df
            if self.is_scanned:
                scale = 4
                img, dpi = page_to_image(page, scale)
                page_df = get_scanned_page_as_df(img, dpi, scale)
            else:
                page_df = page_to_df(page)
            data_df["page_num"] = page.number
            data_df["intersection"] = 0
            data_df["multicolumn"] = 0
            data_df["x1"] = data_df["cv_rect"].apply(lambda rect: rect.x0)
            data_df["x2"] = data_df["cv_rect"].apply(lambda rect: rect.x1)
            data_df["y1"] = data_df["cv_rect"].apply(lambda rect: rect.y0)
            data_df["y2"] = data_df["cv_rect"].apply(lambda rect: rect.y1)
            data_df = self.remove_border_elements(page, data_df)
            data_df = self.add_pagebreak(data_df)
            grouped = data_df.groupby("multicolumn")
            dfs = [grouped.get_group(x) for x in grouped.groups]
            data_df = data_df.iloc[0:0]
            for part_df in dfs:
                part_df = self.normalize_block_width(part_df)
                part_df = self.merge_normalized_rect(part_df, page_df)
                part_df = self.sort_in_reading_order(part_df)
                if data_df.empty:
                    data_df = part_df.copy()
                else:
                    data_df = data_df.append(part_df)
            data_df.reset_index(inplace=True, drop=True)
            return data_df
        except Exception as e:
            logging.error(f"> error in processing page {self.page_num} of {self.file_name}")

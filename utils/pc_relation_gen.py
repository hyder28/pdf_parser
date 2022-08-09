from collections import defaultdict
import logging

args = {"normal": 0, "italic": 2, "bold": 3}
style2int = defaultdict(lambda: 1, **args)


class depthCalculator:
    def __init__(self):
        self.stack = []
        self.parent_holder = {}
        self.depth = 0

    def __update_depth(self):
        if len(self.stack) == 0:
            self.depth = 0
        self.depth = len(self.stack) - 1

    def __update_parent_id(self, parent_id):
        self.parent_holder[self.depth] = parent_id

    def get_title_parent(self, ):
        if self.depth == 0:
            return -1
        return self.parent_holder[self.depth - 1]

    def add_title(self, style, size, is_upper, parent_id, pdf_name):
        try:
            index = -1
            for ind, item in enumerate(self.stack):
                if item[1] < size:
                    index = ind
                    break
                elif item == [style, size, is_upper]:
                    index = ind
                    break
            if index != -1:
                self.stack = self.stack[:index]
            self.stack.append([style, size, is_upper])
            self.__update_depth()
            self.__update_parent_id(parent_id)
            return self.get_title_parent(), self.depth
        except Exception as e:
            logging.error(f"Error in adding parent to depth calculator for {pdf_name}")

    def get_parent_and_depth(self, ):
        if len(self.parent_holder) == 0:
            return -1, 0
        return self.parent_holder[self.depth], self.depth + 1


class PCRelationGen:
    def __init__(self):
        pass

    def __in_border(self, row):
        """Check if a block lies in the border of the page
        Args:
            row : dataframe from Blocksgenerator
        Returns:
            bool: True if the row block lies in the border
        """
        if row["y1"] + row["y2"] > 1400:
            return True
        elif row["y1"] + row["y2"] < 200:
            return True
        else:
            return False

    def __clean_text(self, text):
        return text.replace("(continued)", "").strip()

    def remove_duplicates(self, data_df, pdf_name):
        try:
            title_df = data_df[data_df["label"] == "title"].copy()
            data_df["to_delete"] = False
            for title_ind, title in title_df.iterrows():
                for next_title_ind, next_title in title_df.iterrows():
                    if next_title_ind <= title_ind:
                        continue
                    cur_text = self.__clean_text(next_title["text"])
                    prev_text = self.__clean_text(title["text"])
                    if (cur_text == prev_text and abs(next_title["x1"] - title["x1"]) <= 2 and abs(
                            next_title["y1"] - title["y1"]) <= 2):
                        data_df.at[next_title_ind, "to_delete"] = True
            data_df.drop(data_df[data_df["to_delete"] == True].index, inplace=True)
            data_df.reset_index(drop=True, inplace=True)
            return data_df
        except Exception as e:
            logging.error(f"Cannot remove duplicate headers for {pdf_name}")
            return data_df

    def generate_relationship(self, data_df, pdf_name):
        try:
            try:
                data_df["text"] = data_df["text"].apply(lambda text: bytes(text.replace("\\N", "").encode(
                    "ascii", "backslashreplace").decode("ascii"), "ascii").decode('unicode-escape'))
            except Exception as e:
                logging.error(f"Cannot remove unicode characters for {pdf_name}")
            data_df = self.remove_duplicates(data_df, pdf_name)
            data_df["istyle"] = data_df["style"].apply(lambda x: style2int[x])

            data_df["block_id"] = range(len(data_df))
            data_df["parent_id"] = -1
            data_df["depth"] = -1
            data_df.reset_index(drop=True, inplace=True)
            dc = depthCalculator()
            parent_id = -1
            depth = -1
            prev_table_parent_depth = [-1, -1]
            for index, row in data_df.iterrows():
                if row["label"] == "table_image":
                    parent_id, depth = prev_table_parent_depth
                    # continue
                elif row["label"] == "text" or row["label"] == "table":
                    parent_id, depth = dc.get_parent_and_depth()
                    prev_table_parent_depth = [parent_id, depth]
                elif row["label"] == "title":
                    parent_id, depth = dc.add_title(
                        row["istyle"], row["size"],
                        row["text"].isupper(), row["block_id"], pdf_name)
                data_df.at[index, "parent_id"] = parent_id
                data_df.at[index, "depth"] = depth
            data_df.reset_index(inplace=True, drop=True)
            df = data_df[[
                "block_id",
                "parent_id",
                "depth",
                "label",
                "text",
                "page_no",
            ]]

        except Exception as e:
            logging.error(f"Error in generating parent-child relationships for {pdf_name}")

        return df

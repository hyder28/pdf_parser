from fastapi import FastAPI, UploadFile
from typing import Union
import uvicorn

from utils.run_pdf_parse import get_pdf_extraction
from utils.config import temp_folder

from datetime import datetime
from uuid import uuid4
import logging
import os

app = FastAPI()


@app.get("/")
def root() -> dict:
    return {"message": "Lets parse PDF documents!"}


@app.get("/health")
def check_health() -> dict:
    """
    Checks health
    """
    return {"status": "OK"}


@app.post("/extract_pdf")
async def extract_pdf(pdf: Union[UploadFile, None] = None) -> dict:
    """
    Extracts pdf to parent-child relationships
    """
    logging.basicConfig(filename="parser_app.log", level=logging.DEBUG)
    logging.info(f"Started at {str(datetime.now())}")

    if not pdf:
        logging.error("> error in pdf file upload")
        return {"message": "No PDF file uploaded"}

    pdf_fname = pdf.filename

    if not pdf_fname.endswith(".pdf"):
        logging.error("> error in pdf file upload")
        return {"message": "Incorrect file uploaded"}
    else:
        pdf_fname = pdf_fname[:-4]

    temp_pdf_file = os.path.join(temp_folder, f"{uuid4()}.pdf")

    with open(temp_pdf_file, "wb") as file:
        file.write(pdf.file.read())

    df_result = get_pdf_extraction(temp_pdf_file,  pdf_fname)
    dict_result = df_result.to_dict(orient="records")

    for f in os.listdir(temp_folder):
        os.remove(os.path.join(temp_folder, f))

    logging.info(f"Ended at {str(datetime.now())}")

    return dict_result


if __name__ == "__main__":
    uvicorn.run(app, port=5000)

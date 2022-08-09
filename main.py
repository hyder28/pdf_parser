import uvicorn
import logging
import os

from fastapi import FastAPI, UploadFile
from utils.run_pdf_parse import get_pdf_extraction

from datetime import datetime

app = FastAPI()


@app.get("/health")
def check_health() -> dict:
    """
    Checks health
    """
    return {"status": "OK"}


@app.post("/extract_pdf")
async def extract_pdf(pdf: UploadFile) -> dict:
    """
    Extracts pdf to parent-child relationships
    """
    logging.basicConfig(filename="parser_app.log", level=logging.DEBUG)
    logging.info(f"Started at {str(datetime.now())}")

    pdf_fpath = os.path.join("./pdf_files", pdf.filename)
    pdf_fname = pdf.filename[:-4]

    df_result = get_pdf_extraction(pdf_fpath, pdf_fname)
    dict_result = df_result.to_dict(orient="records")

    logging.info(f"Ended at {str(datetime.now())}")

    return dict_result


if __name__ == "__main__":
    uvicorn.run(app, port=5000)

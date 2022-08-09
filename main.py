import uvicorn
from fastapi import FastAPI, UploadFile

from utils.run_pdf_parse import get_pdf_extraction

import os

app = FastAPI()


@app.get("/health_check")
def check_health():
    return {"status": "OK"}


@app.post("/extract_pdf")
async def extract_pdf(pdf: UploadFile):
    pdf_fpath = os.path.join("./pdf_files", pdf.filename)
    pdf_fname = pdf.filename[:-4]

    df_result = get_pdf_extraction(pdf_fpath, pdf_fname)
    json_result = df_result.to_json(orient="records")

    return json_result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

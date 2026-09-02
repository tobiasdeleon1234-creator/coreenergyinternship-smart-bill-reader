import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.services.gemini_extractor import extract_bill


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024
ALLOWED_TYPES = {"image/png", "image/jpeg", "application/pdf"}

app = FastAPI(title="Smart Bill Reader", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


def _looks_like_declared_type(data: bytes, content_type: str) -> bool:
    if content_type == "application/pdf":
        return data.startswith(b"%PDF-")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    return False


@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    content_type = (file.content_type or "").lower()

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Please upload a PNG, JPG/JPEG, or PDF.",
        )

    data = await file.read(MAX_FILE_SIZE + 1)

    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    if len(data) > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Maximum allowed size is {max_mb} MB.",
        )

    if not _looks_like_declared_type(data, content_type):
        raise HTTPException(
            status_code=400,
            detail="The file contents do not match the declared file type.",
        )

    try:
        result = await extract_bill(data, content_type)
    except RuntimeError as exc:
        message = str(exc)
        if "GEMINI_API_KEY" in message:
            raise HTTPException(status_code=500, detail=message)
        raise HTTPException(
            status_code=502,
            detail="The AI service could not process this document. Please try again or use a clearer copy.",
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="The document could not be read reliably. Please try another image or PDF.",
        )

    if not result.is_bill_or_invoice:
        raise HTTPException(
            status_code=422,
            detail=result.validation_reason or "This file does not appear to be a bill or invoice.",
        )

    return result.model_dump()

"""
OCR Route — /api/ocr/upload
Accepts image upload, runs OCR, extracts healthcare parameters,
saves scan to Supabase, returns structured result.
"""

import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Optional

from ocr.engine import OCREngine
from ocr.extractor import HealthcareParameterExtractor
from api.schemas import OCRUploadResponse, OCRResult, ExtractedParams
from db.supabase_client import SupabaseClient

router = APIRouter()
logger = logging.getLogger(__name__)

# Module-level singletons (loaded once per worker)
_ocr_engine = None
_extractor = None


def get_ocr_engine() -> OCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine(lang="en")
    return _ocr_engine


def get_extractor() -> HealthcareParameterExtractor:
    global _extractor
    if _extractor is None:
        _extractor = HealthcareParameterExtractor()
    return _extractor


ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/jpg",
    "image/tiff", "image/bmp", "image/webp",
    "application/pdf",
}
MAX_SIZE_MB = 10


@router.post("/upload", response_model=OCRUploadResponse)
async def upload_medical_image(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    document_type: Optional[str] = Form("medical_report"),
):
    """
    Upload a medical image or scanned report.
    Returns extracted healthcare parameters ready for ML prediction.
    """
    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Accepted: JPEG, PNG, TIFF, BMP, WebP, PDF"
        )

    # Read file
    image_bytes = await file.read()

    # Validate size
    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum: {MAX_SIZE_MB} MB"
        )

    # Generate unique scan ID
    scan_id = str(uuid.uuid4())

    try:
        # Step 1: OCR
        logger.info(f"[{scan_id}] Starting OCR on {file.filename}")
        engine = get_ocr_engine()
        ocr_result_raw = engine.extract_text(image_bytes)

        ocr_result = OCRResult(
            raw_text=ocr_result_raw["raw_text"],
            lines=ocr_result_raw["lines"],
            confidence=round(ocr_result_raw["confidence"], 3),
            engine_used=ocr_result_raw["engine_used"],
            preprocessed=ocr_result_raw.get("preprocessed", False),
        )
        logger.info(
            f"[{scan_id}] OCR complete. Engine: {ocr_result.engine_used}, "
            f"Confidence: {ocr_result.confidence:.2f}"
        )

        # Step 2: Parameter extraction
        extractor = get_extractor()
        raw_params = extractor.extract(ocr_result.raw_text)
        params_dict = raw_params.to_dict()
        params_dict["completeness_score"] = raw_params.completeness_score()

        extracted = ExtractedParams(**params_dict)
        ready = extracted.completeness_score >= 0.3

        # Step 3: Save to Supabase (non-blocking best-effort)
        try:
            db = SupabaseClient()
            await db.save_scan(
                scan_id=scan_id,
                user_id=user_id,
                document_type=document_type,
                filename=file.filename,
                ocr_text=ocr_result.raw_text,
                ocr_confidence=ocr_result.confidence,
                ocr_engine=ocr_result.engine_used,
                extracted_params=params_dict,
            )
        except Exception as db_err:
            logger.warning(f"[{scan_id}] Supabase save failed (non-fatal): {db_err}")

        return OCRUploadResponse(
            scan_id=scan_id,
            ocr=ocr_result,
            extracted=extracted,
            ready_to_predict=ready,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[{scan_id}] OCR pipeline failed")
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {str(e)}"
        )


@router.get("/scan/{scan_id}", summary="Retrieve a previous scan result")
async def get_scan(scan_id: str):
    """Fetch stored OCR result by scan ID (from Supabase)."""
    try:
        db = SupabaseClient()
        scan = await db.get_scan(scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        return scan
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

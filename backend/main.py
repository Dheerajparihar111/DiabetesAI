"""
DiabetesSense AI — FastAPI Backend
Main application entry point with all route registrations.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os

from api.routes import ocr, predict, health_score, recommendations, gamification
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DiabetesSense AI",
    description="OCR-powered diabetes risk prediction API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow your React/Next.js frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(ocr.router,             prefix="/api/ocr",             tags=["OCR"])
app.include_router(predict.router,         prefix="/api/predict",         tags=["Prediction"])
app.include_router(health_score.router,    prefix="/api/health-score",    tags=["Health Score"])
app.include_router(recommendations.router, prefix="/api/recommendations",  tags=["Recommendations"])
app.include_router(gamification.router,    prefix="/api/gamification",    tags=["Gamification"])


@app.get("/", tags=["System"])
async def root():
    return {"status": "ok", "service": "DiabetesSense AI v2.0"}


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}

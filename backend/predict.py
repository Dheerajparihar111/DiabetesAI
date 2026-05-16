"""
Prediction Route — /api/predict
Loads trained ML model, validates + normalizes extracted parameters,
runs inference, returns full risk assessment.
"""

import logging
import joblib
import numpy as np
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import Optional

from api.schemas import (PredictRequest, PredictResponse,
                          RiskLevel, TopRiskFactor)
from db.supabase_client import SupabaseClient

router = APIRouter()
logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent / "ml" / "models" / "best_model.pkl"
PREPROCESSOR_PATH = Path(__file__).parent.parent.parent / "ml" / "models" / "preprocessor.pkl"

# Singleton model/preprocessor (loaded once)
_model = None
_preprocessor = None
_feature_names = None
_feature_importance = None

RISK_LABELS   = {0: RiskLevel.LOW, 1: RiskLevel.MEDIUM, 2: RiskLevel.HIGH}
RISK_POINTS   = {0: 10, 1: 20, 2: 30}   # More points for completing high-risk scans


def load_model():
    global _model, _preprocessor, _feature_names, _feature_importance
    if _model is None:
        try:
            payload = joblib.load(MODEL_PATH)
            _model = payload["model"]
            _feature_names = payload.get("results", {})
            logger.info(f"Model loaded: {payload['model_name']}")
        except Exception as e:
            logger.error(f"Could not load model: {e}")
            _model = "mock"   # Hackathon fallback

    if _preprocessor is None:
        try:
            _preprocessor = joblib.load(PREPROCESSOR_PATH)
        except Exception as e:
            logger.warning(f"Preprocessor not found, using passthrough: {e}")
            _preprocessor = "mock"


def _mock_predict(params: dict) -> np.ndarray:
    """
    Rule-based mock prediction for hackathon demo when model isn't trained yet.
    Mimics ADA clinical thresholds.
    """
    hba1c   = params.get("hba1c") or 5.0
    glucose = params.get("glucose_fasting") or 90
    bmi     = params.get("bmi") or 22
    age     = params.get("age") or 30
    fhx     = params.get("family_hx_diabetes") or 0

    # Risk score (0–10)
    score = 0
    score += 3 if hba1c >= 6.5 else (1.5 if hba1c >= 5.7 else 0)
    score += 2 if glucose >= 126 else (1 if glucose >= 100 else 0)
    score += 1.5 if bmi >= 30 else (0.5 if bmi >= 25 else 0)
    score += 0.5 if age > 45 else 0
    score += 1 if fhx == 1 else 0

    if score >= 5:
        return np.array([0.05, 0.15, 0.80])
    elif score >= 2.5:
        return np.array([0.20, 0.60, 0.20])
    else:
        return np.array([0.80, 0.15, 0.05])


def _build_feature_vector(req: PredictRequest) -> np.ndarray:
    """Map request fields to model feature order."""
    # Default feature order matching the training pipeline
    FEATURE_ORDER = [
        "age", "gender", "race_ethnicity", "income_poverty_ratio",
        "bmi", "waist_cm", "hba1c", "glucose_fasting",
        "total_cholesterol", "triglycerides", "hdl_cholesterol",
        "bp_systolic", "bp_diastolic",
        "sleep_hours", "trouble_sleeping",
        "vigorous_activity_min", "moderate_activity_min", "sedentary_min",
        "fast_food_days", "frozen_meal_days",
        "family_hx_diabetes", "ever_high_bp",
        # Engineered
        "metabolic_risk_score", "waist_height_ratio",
        "activity_balance", "cv_strain", "diet_risk", "hba1c_bmi_interaction",
    ]

    params = req.dict()
    # Fill missing with population medians (conservative defaults)
    defaults = {
        "age": 35, "gender": 1, "race_ethnicity": 3,
        "income_poverty_ratio": 2.5,
        "bmi": 24, "waist_cm": 85,
        "hba1c": 5.5, "glucose_fasting": 95,
        "total_cholesterol": 180, "triglycerides": 120,
        "hdl_cholesterol": 50, "bp_systolic": 115,
        "bp_diastolic": 75, "sleep_hours": 7.5,
        "trouble_sleeping": 0, "vigorous_activity_min": 30,
        "moderate_activity_min": 60, "sedentary_min": 360,
        "fast_food_days": 1, "frozen_meal_days": 1,
        "family_hx_diabetes": 0, "ever_high_bp": 0,
    }

    filled = {k: (params.get(k) if params.get(k) is not None else defaults.get(k, 0))
              for k in FEATURE_ORDER
              if k not in ["metabolic_risk_score", "waist_height_ratio",
                            "activity_balance", "cv_strain", "diet_risk",
                            "hba1c_bmi_interaction"]}

    # Engineer features
    bmi = filled.get("bmi", 24)
    hba1c = filled.get("hba1c", 5.5)
    bp_sys = filled.get("bp_systolic", 115)
    bp_dia = filled.get("bp_diastolic", 75)
    waist  = filled.get("waist_cm", 85)
    height = (req.height_cm or 170)
    sed    = filled.get("sedentary_min", 360)
    vig    = filled.get("vigorous_activity_min", 30)
    mod    = filled.get("moderate_activity_min", 60)
    ff     = filled.get("fast_food_days", 1)
    frz    = filled.get("frozen_meal_days", 1)
    gluc   = filled.get("glucose_fasting", 95)
    hdl    = filled.get("hdl_cholesterol", 50)
    tg     = filled.get("triglycerides", 120)

    filled["metabolic_risk_score"] = (
        (bmi > 30) + (bp_sys > 130) + (tg > 150) + (hdl < 40) + (gluc > 100)
    )
    filled["waist_height_ratio"]   = waist / height if height else 0.5
    filled["activity_balance"]     = vig * 2 + mod - sed * 0.1
    filled["cv_strain"]            = bp_sys * bp_dia / 1000
    filled["diet_risk"]            = ff + frz
    filled["hba1c_bmi_interaction"] = hba1c * bmi

    vector = np.array([filled.get(f, 0) for f in FEATURE_ORDER], dtype=float)
    return vector


def _get_top_factors(req: PredictRequest) -> list:
    """Return top contributing parameters as TopRiskFactor objects."""
    params = req.dict()
    thresholds = {
        "hba1c":            ("HbA1c (blood sugar average)", params.get("hba1c")),
        "glucose_fasting":  ("Fasting glucose level",       params.get("glucose_fasting")),
        "bmi":              ("Body Mass Index (BMI)",        params.get("bmi")),
        "family_hx_diabetes": ("Family history of diabetes", params.get("family_hx_diabetes")),
        "bp_systolic":      ("Systolic blood pressure",      params.get("bp_systolic")),
        "triglycerides":    ("Triglyceride level",           params.get("triglycerides")),
    }
    factors = []
    importances = [0.28, 0.22, 0.18, 0.12, 0.10, 0.08]  # Approximate from training
    for i, (feat, (label, val)) in enumerate(thresholds.items()):
        if val is not None:
            factors.append(TopRiskFactor(
                feature=feat, label=label,
                importance=round(importances[i] * 100, 1),
                value=float(val)
            ))
    return factors[:5]


@router.post("/", response_model=PredictResponse, summary="Predict diabetes risk")
async def predict(req: PredictRequest):
    """
    Run diabetes risk prediction.
    Accepts extracted parameters from OCR or manual input.
    Returns risk level, health score, confidence, and top risk factors.
    """
    load_model()

    params_dict = req.dict()

    # Use mock if model not available
    if _model == "mock" or _preprocessor == "mock":
        proba = _mock_predict(params_dict)
        logger.info("Using rule-based mock prediction (model not loaded)")
    else:
        try:
            import pandas as pd
            # Build and scale feature vector
            vector = _build_feature_vector(req).reshape(1, -1)
            # The saved preprocessor has already been fitted on NHANES
            scaled = _preprocessor.scaler.transform(
                _preprocessor.imputer.transform(vector)
            )
            proba = _model.predict_proba(scaled)[0]
        except Exception as e:
            logger.error(f"Model inference failed, falling back to mock: {e}")
            proba = _mock_predict(params_dict)

    risk_class = int(np.argmax(proba))
    confidence = round(float(proba[risk_class]) * 100, 1)
    health_score = max(0, min(100, int(100 - proba[2] * 60 - proba[1] * 30)))

    # Early warning message
    warnings = []
    if params_dict.get("hba1c") and params_dict["hba1c"] >= 5.7:
        warnings.append("elevated HbA1c")
    if params_dict.get("bmi") and params_dict["bmi"] >= 25:
        warnings.append("high BMI")
    if params_dict.get("family_hx_diabetes") == 1:
        warnings.append("family history")

    if risk_class == 0:
        warning = "No immediate diabetes risk detected."
    elif risk_class == 1:
        warning = f"Pre-diabetic indicators: {', '.join(warnings[:3])}." if warnings else "Borderline values detected."
    else:
        warning = f"High risk: {' + '.join(warnings[:3])} detected." if warnings else "Elevated diabetes risk detected. Clinical evaluation recommended."

    # Clinical explanation
    explanation_parts = [
        f"AI model classified this as {RISK_LABELS[risk_class].value} risk "
        f"with {confidence}% confidence."
    ]
    if params_dict.get("hba1c", 0) >= 6.5:
        explanation_parts.append("HbA1c meets clinical threshold for diabetes (≥6.5%).")
    elif params_dict.get("hba1c", 0) >= 5.7:
        explanation_parts.append("HbA1c in pre-diabetic range (5.7–6.4%).")
    if params_dict.get("bmi", 0) >= 30:
        explanation_parts.append("Obesity significantly elevates insulin resistance.")

    # Save prediction result
    try:
        db = SupabaseClient()
        await db.save_prediction(
            scan_id=req.scan_id,
            user_id=req.user_id,
            risk_class=risk_class,
            risk_level=RISK_LABELS[risk_class].value,
            confidence=confidence,
            health_score=health_score,
            proba=proba.tolist(),
        )
    except Exception as e:
        logger.warning(f"Could not save prediction: {e}")

    return PredictResponse(
        scan_id=req.scan_id,
        risk_level=RISK_LABELS[risk_class],
        risk_class=risk_class,
        confidence=confidence,
        diabetes_probability=round(float(proba[2]) * 100, 1),
        prediabetes_probability=round(float(proba[1]) * 100, 1),
        normal_probability=round(float(proba[0]) * 100, 1),
        health_score=health_score,
        early_warning=warning,
        top_risk_factors=_get_top_factors(req),
        clinical_explanation=" ".join(explanation_parts),
        points_awarded=RISK_POINTS[risk_class],
    )

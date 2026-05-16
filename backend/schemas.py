"""
API Schemas — DiabetesSense AI
All Pydantic models for request validation and response serialization.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from enum import Enum


# ── Enums ────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW    = "Low"
    MEDIUM = "Medium"
    HIGH   = "High"


class RecommendationPriority(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


# ── OCR ──────────────────────────────────────────────────────────────────────

class OCRResult(BaseModel):
    raw_text:       str
    lines:          List[str]
    confidence:     float
    engine_used:    str
    preprocessed:   bool


class ExtractedParams(BaseModel):
    glucose_fasting:     Optional[float] = None
    glucose_random:      Optional[float] = None
    hba1c:               Optional[float] = None
    bmi:                 Optional[float] = None
    weight_kg:           Optional[float] = None
    height_cm:           Optional[float] = None
    age:                 Optional[int]   = None
    bp_systolic:         Optional[int]   = None
    bp_diastolic:        Optional[int]   = None
    total_cholesterol:   Optional[float] = None
    hdl_cholesterol:     Optional[float] = None
    ldl_cholesterol:     Optional[float] = None
    triglycerides:       Optional[float] = None
    insulin:             Optional[float] = None
    family_hx_diabetes:  Optional[int]   = None
    gender:              Optional[int]   = None
    extraction_notes:    List[str]       = []
    completeness_score:  float           = 0.0


class OCRUploadResponse(BaseModel):
    scan_id:         str
    ocr:             OCRResult
    extracted:       ExtractedParams
    ready_to_predict: bool    # True if completeness >= 0.4


# ── Prediction ───────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    """Direct prediction without OCR — manual input fallback."""
    scan_id:             Optional[str]   = None
    user_id:             Optional[str]   = None
    glucose_fasting:     Optional[float] = None
    hba1c:               Optional[float] = None
    bmi:                 Optional[float] = None
    age:                 Optional[int]   = None
    bp_systolic:         Optional[int]   = None
    bp_diastolic:        Optional[int]   = None
    total_cholesterol:   Optional[float] = None
    triglycerides:       Optional[float] = None
    hdl_cholesterol:     Optional[float] = None
    family_hx_diabetes:  Optional[int]   = Field(None, ge=0, le=1)
    gender:              Optional[int]   = Field(None, ge=1, le=2)
    weight_kg:           Optional[float] = None
    height_cm:           Optional[float] = None
    sleep_hours:         Optional[float] = None
    sedentary_min:       Optional[float] = None

    @validator('hba1c')
    def hba1c_range(cls, v):
        if v is not None and not (3.0 <= v <= 20.0):
            raise ValueError(f"HbA1c {v} out of valid range (3–20%)")
        return v

    @validator('bmi')
    def bmi_range(cls, v):
        if v is not None and not (10.0 <= v <= 70.0):
            raise ValueError(f"BMI {v} out of valid range (10–70)")
        return v


class TopRiskFactor(BaseModel):
    feature:    str
    label:      str
    importance: float
    value:      Optional[float]


class PredictResponse(BaseModel):
    scan_id:               Optional[str]
    risk_level:            RiskLevel
    risk_class:            int
    confidence:            float           # 0–100
    diabetes_probability:  float           # 0–100
    prediabetes_probability: float
    normal_probability:    float
    health_score:          int             # 0–100
    early_warning:         str
    top_risk_factors:      List[TopRiskFactor]
    clinical_explanation:  str
    points_awarded:        int             # gamification


# ── Health Score ─────────────────────────────────────────────────────────────

class HealthScoreResponse(BaseModel):
    user_id:          Optional[str]
    health_score:     int
    score_breakdown:  Dict[str, Any]
    trend:            str              # "improving" | "stable" | "worsening"
    badge:            Optional[str]


# ── Recommendations ──────────────────────────────────────────────────────────

class Recommendation(BaseModel):
    category:   str
    icon:       str
    action:     str
    detail:     str
    priority:   RecommendationPriority
    game_points: int                   # points for completing this action


class RecommendationsRequest(BaseModel):
    risk_level:          RiskLevel
    extracted_params:    Optional[ExtractedParams] = None
    user_preferences:    Optional[Dict[str, Any]]  = None


class RecommendationsResponse(BaseModel):
    risk_level:      RiskLevel
    recommendations: List[Recommendation]
    ai_message:      str           # Friendly coach message
    daily_goal:      str


# ── Gamification ─────────────────────────────────────────────────────────────

class MissionStatus(str, Enum):
    PENDING    = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED  = "completed"


class Mission(BaseModel):
    id:          str
    title:       str
    description: str
    points:      int
    status:      MissionStatus
    category:    str


class GamificationProfile(BaseModel):
    user_id:         str
    total_points:    int
    level:           int
    level_name:      str
    streak_days:     int
    scans_completed: int
    missions:        List[Mission]
    badges:          List[str]
    rank:            Optional[int]
    next_level_pts:  int

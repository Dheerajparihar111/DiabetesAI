from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import joblib

# =========================
# LOAD TRAINED MODEL
# =========================

model = joblib.load("../model/diabetes_model.pkl")

# =========================
# CREATE FASTAPI APP
# =========================

app = FastAPI()

# =========================
# INPUT FORMAT
# =========================

class HealthData(BaseModel):
    glucose: float
    bmi: float
    age: int
    blood_pressure: float

# =========================
# PREDICTION API
# =========================

@app.post("/predict")
def predict(data: HealthData):

    # Convert input to array
    features = np.array([[
        data.glucose,
        data.bmi,
        data.age,
        data.blood_pressure
    ]])

    # AI Prediction
    prediction = model.predict(features)[0]

    # Probability
    probability = model.predict_proba(features)[0][1]

    # Risk Level
    risk = "Low"

    if probability > 0.7:
        risk = "High"

    elif probability > 0.4:
        risk = "Medium"

    # Return result
    return {
        "prediction": int(prediction),
        "risk_level": risk,
        "probability": float(probability)
    }
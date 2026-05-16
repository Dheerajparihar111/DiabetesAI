from fastapi import FastAPI, UploadFile, File
import shutil
import os
import joblib
import pandas as pd
import easyocr
import re

app = FastAPI()

# Create uploads folder automatically
os.makedirs("uploads", exist_ok=True)

# Load model
model = joblib.load("../model/diabetes_model.pkl")

# OCR Reader
reader = easyocr.Reader(['en'])

@app.get("/")
def home():
    return {"message": "Diabetes AI Running"}

@app.post("/predict-image")
async def predict_image(file: UploadFile = File(...)):

    # Save uploaded file
    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # OCR
    result = reader.readtext(file_path)

    text = ""

    for item in result:
        text += item[1] + " "

    # Extract values using regex
    glucose = re.search(r'glucose[:\s]*(\d+)', text, re.I)
    bmi = re.search(r'bmi[:\s]*(\d+\.?\d*)', text, re.I)
    age = re.search(r'age[:\s]*(\d+)', text, re.I)
    bp = re.search(r'blood pressure[:\s]*(\d+)', text, re.I)

    values = {
        "Glucose": int(glucose.group(1)) if glucose else 120,
        "BMI": float(bmi.group(1)) if bmi else 25,
        "Age": int(age.group(1)) if age else 30,
        "BloodPressure": int(bp.group(1)) if bp else 80
    }

    # Predict
    df = pd.DataFrame([values])

    prediction = model.predict(df)[0]

    probability = model.predict_proba(df)[0][1]

    # Recommendations
    recommendations = []

    if probability > 0.7:
        recommendations = [
            "Reduce sugary drinks",
            "Exercise daily",
            "Sleep 8 hours",
            "Avoid junk food"
        ]
    else:
        recommendations = [
            "Maintain healthy lifestyle",
            "Stay hydrated"
        ]

    return {
        "ocr_text": text,
        "values": values,
        "prediction": int(prediction),
        "probability": float(probability),
        "recommendations": recommendations
    }
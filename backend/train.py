import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

# =========================
# LOAD DATASET
# =========================

df = pd.read_csv("../dataset/diabetes.csv")

print("Dataset Loaded Successfully\n")

print(df.head())

# =========================
# SELECT FEATURES
# =========================

X = df[['Glucose', 'BMI', 'Age', 'BloodPressure']]

# Target column
y = df['Outcome']

# =========================
# SPLIT DATA
# =========================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

# =========================
# CREATE AI MODEL
# =========================

model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

# =========================
# TRAIN MODEL
# =========================

model.fit(X_train, y_train)

print("\nAI Model Trained Successfully")

# =========================
# MAKE PREDICTIONS
# =========================

predictions = model.predict(X_test)

# =========================
# CHECK ACCURACY
# =========================

accuracy = accuracy_score(y_test, predictions)

print("\nModel Accuracy:", accuracy)

print("\nClassification Report:\n")

print(classification_report(y_test, predictions))

# =========================
# SAVE MODEL
# =========================

joblib.dump(model, "../model/diabetes_model.pkl")

print("\nModel Saved Successfully!")
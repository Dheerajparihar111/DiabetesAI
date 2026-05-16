// DiabetesSense AI — Upload & Prediction Dashboard
// Single-page React component combining upload, OCR preview,
// risk dashboard, and AI recommendation cards.
// Drop this into your existing React/Next.js project.

import { useState, useCallback } from "react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

// ── API helpers ──────────────────────────────────────────────

async function uploadImage(file, userId) {
  const form = new FormData();
  form.append("file", file);
  if (userId) form.append("user_id", userId);
  form.append("document_type", "medical_report");

  const res = await fetch(`${API_BASE}/api/ocr/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function runPrediction(extractedParams, scanId, userId) {
  const payload = {
    scan_id: scanId,
    user_id: userId,
    ...extractedParams,
    glucose_fasting: extractedParams.glucose_fasting,
    hba1c: extractedParams.hba1c,
    bmi: extractedParams.bmi,
    age: extractedParams.age,
    bp_systolic: extractedParams.bp_systolic,
    bp_diastolic: extractedParams.bp_diastolic,
    total_cholesterol: extractedParams.total_cholesterol,
    triglycerides: extractedParams.triglycerides,
    family_hx_diabetes: extractedParams.family_hx_diabetes,
  };

  const res = await fetch(`${API_BASE}/api/predict/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function getRecommendations(riskLevel, extractedParams) {
  const res = await fetch(`${API_BASE}/api/recommendations/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      risk_level: riskLevel,
      extracted_params: extractedParams,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Sub-components ───────────────────────────────────────────

function RiskMeter({ score, riskLevel }) {
  const color = {
    Low: "#3B6D11",
    Medium: "#854F0B",
    High: "#A32D2D",
  }[riskLevel] || "#888";

  const dialAngle = -135 + (score / 100) * 270;

  return (
    <div style={{ textAlign: "center", padding: "1rem 0" }}>
      <svg viewBox="0 0 200 130" width="200" height="130">
        {/* Background arc */}
        <path
          d="M 20 110 A 80 80 0 1 1 180 110"
          fill="none"
          stroke="#e0e0e0"
          strokeWidth="14"
          strokeLinecap="round"
        />
        {/* Risk arc segments */}
        <path d="M 20 110 A 80 80 0 0 1 69 36" fill="none" stroke="#639922" strokeWidth="14" strokeLinecap="butt"/>
        <path d="M 69 36 A 80 80 0 0 1 131 36" fill="none" stroke="#EF9F27" strokeWidth="14" strokeLinecap="butt"/>
        <path d="M 131 36 A 80 80 0 0 1 180 110" fill="none" stroke="#E24B4A" strokeWidth="14" strokeLinecap="butt"/>
        {/* Needle */}
        <g transform={`rotate(${dialAngle}, 100, 110)`}>
          <line x1="100" y1="110" x2="100" y2="42" stroke={color} strokeWidth="3" strokeLinecap="round"/>
          <circle cx="100" cy="110" r="6" fill={color}/>
        </g>
      </svg>
      <p style={{ margin: "4px 0 0", fontWeight: 500, fontSize: 22, color }}>
        {score}
        <span style={{ fontSize: 14, fontWeight: 400, color: "#888" }}>/100</span>
      </p>
      <p style={{ margin: "2px 0 0", fontSize: 13, color: "#888" }}>Health score</p>
      <span style={{
        display: "inline-block",
        marginTop: 8,
        padding: "4px 14px",
        borderRadius: 20,
        fontSize: 13,
        fontWeight: 500,
        background: riskLevel === "Low" ? "#EAF3DE" : riskLevel === "Medium" ? "#FAEEDA" : "#FCEBEB",
        color,
      }}>
        {riskLevel} risk
      </span>
    </div>
  );
}

function ExtractedParamCard({ label, value, unit, normal }) {
  const hasValue = value !== null && value !== undefined;
  return (
    <div style={{
      background: "var(--color-background-secondary, #f8f8f6)",
      borderRadius: 8,
      padding: "10px 14px",
    }}>
      <p style={{ margin: 0, fontSize: 12, color: "#888" }}>{label}</p>
      <p style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 500 }}>
        {hasValue ? `${value} ${unit || ""}` : <span style={{ color: "#bbb", fontSize: 14 }}>Not found</span>}
      </p>
      {hasValue && normal && (
        <p style={{ margin: "2px 0 0", fontSize: 11, color: "#888" }}>Normal: {normal}</p>
      )}
    </div>
  );
}

function RecommendationCard({ rec, onComplete }) {
  const [done, setDone] = useState(false);
  const priorityColor = {
    critical: "#A32D2D",
    high: "#854F0B",
    medium: "#185FA5",
    low: "#3B6D11",
  }[rec.priority] || "#888";

  return (
    <div style={{
      background: "var(--color-background-primary, #fff)",
      border: "0.5px solid var(--color-border-tertiary, #e0e0e0)",
      borderLeft: `3px solid ${priorityColor}`,
      borderRadius: 8,
      padding: "12px 16px",
      opacity: done ? 0.6 : 1,
      transition: "opacity 0.3s",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <span style={{ fontSize: 22 }}>{rec.icon}</span>
        <div style={{ flex: 1 }}>
          <p style={{ margin: 0, fontWeight: 500, fontSize: 14 }}>{rec.action}</p>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "#666", lineHeight: 1.5 }}>
            {rec.detail}
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
            <span style={{ fontSize: 12, color: priorityColor, fontWeight: 500 }}>
              {rec.priority.charAt(0).toUpperCase() + rec.priority.slice(1)} priority
            </span>
            <span style={{ fontSize: 12, color: "#3B6D11" }}>+{rec.game_points} pts</span>
          </div>
        </div>
        <button
          onClick={() => { setDone(true); onComplete && onComplete(rec); }}
          disabled={done}
          style={{
            padding: "4px 10px",
            fontSize: 12,
            border: "0.5px solid #ccc",
            borderRadius: 6,
            cursor: done ? "default" : "pointer",
            background: done ? "#EAF3DE" : "transparent",
          }}
        >
          {done ? "✓ Done" : "Mark done"}
        </button>
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────

export default function DiabetesSenseDashboard({ userId }) {
  const [stage, setStage] = useState("upload"); // upload|ocr|predict|results
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [ocrResult, setOcrResult] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [earnedPoints, setEarnedPoints] = useState(0);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0] || e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setError(null);
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const ocr = await uploadImage(file, userId);
      setOcrResult(ocr);
      setStage("ocr");
    } catch (err) {
      setError(`Upload failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePredict = async () => {
    setLoading(true);
    setError(null);
    try {
      const pred = await runPrediction(
        ocrResult.extracted,
        ocrResult.scan_id,
        userId
      );
      setPrediction(pred);

      const recs = await getRecommendations(
        pred.risk_level,
        ocrResult.extracted
      );
      setRecommendations(recs);
      setEarnedPoints(pred.points_awarded || 0);
      setStage("results");
    } catch (err) {
      setError(`Prediction failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRecommendationComplete = (rec) => {
    setEarnedPoints((p) => p + (rec.game_points || 0));
  };

  const reset = () => {
    setStage("upload");
    setFile(null);
    setPreview(null);
    setOcrResult(null);
    setPrediction(null);
    setRecommendations(null);
    setError(null);
  };

  // ── Render stages ──

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "2rem 1rem" }}>
      {/* Header */}
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: 22, fontWeight: 500, margin: 0 }}>
          DiabetesSense AI
        </h1>
        <p style={{ fontSize: 14, color: "#888", margin: "4px 0 0" }}>
          Upload a medical report to get your personalised diabetes risk assessment
        </p>
      </div>

      {/* Progress steps */}
      <div style={{ display: "flex", gap: 8, marginBottom: "2rem" }}>
        {["Upload", "OCR review", "Results"].map((label, i) => {
          const stageIdx = ["upload", "ocr", "results"].indexOf(stage);
          const active = i === stageIdx;
          const done = i < stageIdx;
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{
                width: 24, height: 24, borderRadius: "50%",
                background: done ? "#639922" : active ? "#185FA5" : "#e0e0e0",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 12, color: (done || active) ? "#fff" : "#888",
                fontWeight: 500, flexShrink: 0,
              }}>
                {done ? "✓" : i + 1}
              </div>
              <span style={{ fontSize: 13, color: active ? "#185FA5" : "#888" }}>
                {label}
              </span>
              {i < 2 && <span style={{ color: "#ccc" }}>—</span>}
            </div>
          );
        })}
        {earnedPoints > 0 && (
          <div style={{
            marginLeft: "auto", fontSize: 13, fontWeight: 500,
            color: "#3B6D11", background: "#EAF3DE",
            padding: "4px 12px", borderRadius: 20,
          }}>
            +{earnedPoints} pts earned
          </div>
        )}
      </div>

      {error && (
        <div style={{
          background: "#FCEBEB", border: "0.5px solid #F09595",
          borderRadius: 8, padding: "12px 16px", marginBottom: "1rem",
          color: "#A32D2D", fontSize: 14,
        }}>
          {error}
        </div>
      )}

      {/* STAGE: Upload */}
      {stage === "upload" && (
        <div>
          <div
            onDrop={onDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => document.getElementById("file-input").click()}
            style={{
              border: "1.5px dashed var(--color-border-secondary, #ccc)",
              borderRadius: 12, padding: "3rem 2rem",
              textAlign: "center", cursor: "pointer",
              background: preview ? "#f8f8f6" : "transparent",
              transition: "background 0.2s",
            }}
          >
            {preview ? (
              <img src={preview} alt="preview" style={{
                maxHeight: 200, maxWidth: "100%",
                borderRadius: 8, objectFit: "contain",
              }} />
            ) : (
              <>
                <div style={{ fontSize: 32, marginBottom: 8 }}>📋</div>
                <p style={{ margin: 0, fontSize: 15, fontWeight: 500 }}>
                  Drop your medical report here
                </p>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "#888" }}>
                  Blood test · glucose report · prescription · handwritten notes
                </p>
                <p style={{ margin: "8px 0 0", fontSize: 12, color: "#aaa" }}>
                  JPEG · PNG · TIFF · BMP · WebP — max 10 MB
                </p>
              </>
            )}
            <input
              id="file-input" type="file"
              accept="image/*,.pdf"
              onChange={onDrop}
              style={{ display: "none" }}
            />
          </div>

          {file && (
            <div style={{ marginTop: "1rem", textAlign: "center" }}>
              <p style={{ fontSize: 13, color: "#888", margin: "0 0 12px" }}>
                {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </p>
              <button onClick={handleUpload} disabled={loading} style={{
                padding: "10px 28px", fontSize: 15, borderRadius: 8,
                background: loading ? "#ccc" : "#185FA5",
                color: "#fff", border: "none", cursor: loading ? "default" : "pointer",
              }}>
                {loading ? "Processing OCR…" : "Analyse report"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* STAGE: OCR Review */}
      {stage === "ocr" && ocrResult && (
        <div>
          <div style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr 1fr" }}>
            {/* OCR text preview */}
            <div style={{
              background: "var(--color-background-secondary, #f8f8f6)",
              borderRadius: 10, padding: "1rem",
              gridColumn: "1 / -1",
            }}>
              <p style={{ margin: "0 0 8px", fontSize: 13, color: "#888" }}>
                OCR text — {ocrResult.ocr.engine_used} ·
                confidence {Math.round(ocrResult.ocr.confidence * 100)}%
              </p>
              <div style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 12, color: "#444",
                maxHeight: 140, overflowY: "auto",
                lineHeight: 1.6, whiteSpace: "pre-wrap",
              }}>
                {ocrResult.ocr.raw_text || "(No text extracted — try a clearer image)"}
              </div>
            </div>

            {/* Extracted parameters */}
            <ExtractedParamCard label="HbA1c" value={ocrResult.extracted.hba1c} unit="%" normal="< 5.7%"/>
            <ExtractedParamCard label="Fasting glucose" value={ocrResult.extracted.glucose_fasting} unit="mg/dL" normal="70–100"/>
            <ExtractedParamCard label="BMI" value={ocrResult.extracted.bmi} normal="18.5–24.9"/>
            <ExtractedParamCard label="Blood pressure" value={ocrResult.extracted.bp_systolic && `${ocrResult.extracted.bp_systolic}/${ocrResult.extracted.bp_diastolic}`} unit="mmHg" normal="< 120/80"/>
            <ExtractedParamCard label="Total cholesterol" value={ocrResult.extracted.total_cholesterol} unit="mg/dL" normal="< 200"/>
            <ExtractedParamCard label="Triglycerides" value={ocrResult.extracted.triglycerides} unit="mg/dL" normal="< 150"/>
          </div>

          <div style={{ marginTop: "1.5rem", display: "flex", gap: 12 }}>
            <button onClick={reset} style={{
              padding: "10px 20px", fontSize: 14, borderRadius: 8,
              border: "0.5px solid #ccc", background: "transparent", cursor: "pointer",
            }}>
              Upload different image
            </button>
            <button onClick={handlePredict} disabled={loading} style={{
              padding: "10px 28px", fontSize: 14, borderRadius: 8,
              background: loading ? "#ccc" : "#185FA5",
              color: "#fff", border: "none", cursor: loading ? "default" : "pointer",
              flex: 1,
            }}>
              {loading ? "Running AI prediction…" : "Get diabetes risk assessment →"}
            </button>
          </div>
        </div>
      )}

      {/* STAGE: Results */}
      {stage === "results" && prediction && (
        <div style={{ display: "grid", gap: "1.5rem" }}>
          {/* Risk meter */}
          <div style={{
            background: "var(--color-background-primary, #fff)",
            border: "0.5px solid var(--color-border-tertiary, #e0e0e0)",
            borderRadius: 12, padding: "1.5rem",
            display: "grid", gridTemplateColumns: "auto 1fr", gap: "1.5rem",
            alignItems: "center",
          }}>
            <RiskMeter score={prediction.health_score} riskLevel={prediction.risk_level}/>
            <div>
              <p style={{ margin: 0, fontSize: 16, fontWeight: 500 }}>
                {prediction.early_warning}
              </p>
              <p style={{ margin: "8px 0 0", fontSize: 13, color: "#666", lineHeight: 1.6 }}>
                {prediction.clinical_explanation}
              </p>
              <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
                <div style={{ fontSize: 13 }}>
                  <span style={{ color: "#888" }}>Diabetes: </span>
                  <span style={{ fontWeight: 500, color: "#A32D2D" }}>
                    {prediction.diabetes_probability}%
                  </span>
                </div>
                <div style={{ fontSize: 13 }}>
                  <span style={{ color: "#888" }}>Pre-diabetic: </span>
                  <span style={{ fontWeight: 500, color: "#854F0B" }}>
                    {prediction.prediabetes_probability}%
                  </span>
                </div>
                <div style={{ fontSize: 13 }}>
                  <span style={{ color: "#888" }}>Normal: </span>
                  <span style={{ fontWeight: 500, color: "#3B6D11" }}>
                    {prediction.normal_probability}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* AI coach message */}
          {recommendations && (
            <div style={{
              background: "#E6F1FB", borderRadius: 10,
              padding: "1rem 1.25rem",
            }}>
              <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: "#0C447C" }}>
                AI Health Coach
              </p>
              <p style={{ margin: "6px 0 0", fontSize: 14, color: "#185FA5", lineHeight: 1.6 }}>
                {recommendations.ai_message}
              </p>
              <p style={{ margin: "10px 0 0", fontSize: 13, color: "#0C447C", fontWeight: 500 }}>
                Today's goal: {recommendations.daily_goal}
              </p>
            </div>
          )}

          {/* Top risk factors */}
          <div>
            <p style={{ margin: "0 0 10px", fontSize: 15, fontWeight: 500 }}>
              Top risk factors
            </p>
            <div style={{ display: "grid", gap: 8 }}>
              {prediction.top_risk_factors.map((f, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ fontSize: 13, color: "#888", minWidth: 160 }}>{f.label}</span>
                  <div style={{ flex: 1, height: 6, background: "#f0f0f0", borderRadius: 3 }}>
                    <div style={{
                      width: `${f.importance}%`, height: "100%",
                      background: "#185FA5", borderRadius: 3,
                    }}/>
                  </div>
                  <span style={{ fontSize: 12, color: "#888", minWidth: 40 }}>
                    {f.importance}%
                  </span>
                  {f.value !== null && (
                    <span style={{ fontSize: 12, color: "#444", minWidth: 50 }}>
                      {f.value}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Recommendations */}
          {recommendations && (
            <div>
              <p style={{ margin: "0 0 10px", fontSize: 15, fontWeight: 500 }}>
                Personalised recommendations
              </p>
              <div style={{ display: "grid", gap: 10 }}>
                {recommendations.recommendations.map((rec, i) => (
                  <RecommendationCard
                    key={i} rec={rec}
                    onComplete={handleRecommendationComplete}
                  />
                ))}
              </div>
            </div>
          )}

          <button onClick={reset} style={{
            padding: "10px 20px", fontSize: 14, borderRadius: 8,
            border: "0.5px solid #ccc", background: "transparent",
            cursor: "pointer", marginTop: "0.5rem",
          }}>
            Analyse another report
          </button>
        </div>
      )}
    </div>
  );
}

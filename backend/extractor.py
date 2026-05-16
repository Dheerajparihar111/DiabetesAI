"""
Healthcare Parameter Extractor — DiabetesSense AI
Parses OCR raw text → structured medical parameters using
regex patterns, unit normalization, and sanity validation.
"""

import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractedParameters:
    """Structured output of the NLP extraction stage."""
    glucose_fasting:     Optional[float] = None   # mg/dL
    glucose_random:      Optional[float] = None   # mg/dL
    hba1c:               Optional[float] = None   # %
    bmi:                 Optional[float] = None
    weight_kg:           Optional[float] = None
    height_cm:           Optional[float] = None
    age:                 Optional[int]   = None
    bp_systolic:         Optional[int]   = None
    bp_diastolic:        Optional[int]   = None
    total_cholesterol:   Optional[float] = None   # mg/dL
    hdl_cholesterol:     Optional[float] = None
    ldl_cholesterol:     Optional[float] = None
    triglycerides:       Optional[float] = None
    insulin:             Optional[float] = None   # µIU/mL
    creatinine:          Optional[float] = None
    family_hx_diabetes:  Optional[int]   = None   # 0 or 1
    gender:              Optional[int]   = None   # 1=Male, 2=Female
    extraction_notes:    list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def completeness_score(self) -> float:
        """Fraction of core fields successfully extracted."""
        core = ['glucose_fasting', 'hba1c', 'bmi', 'age',
                'bp_systolic', 'total_cholesterol']
        found = sum(1 for f in core if getattr(self, f) is not None)
        return round(found / len(core), 2)


class HealthcareParameterExtractor:
    """
    Two-pass extraction:
    Pass 1 — strict regex for labelled values ("Glucose: 120 mg/dL")
    Pass 2 — contextual regex for tabular / unlabelled formats
    """

    # ── Regex patterns ──────────────────────────────────────────────────────

    PATTERNS = {
        'glucose_fasting': [
            r'(?:fasting[\s\-]*(?:blood[\s]*)?(?:glucose|sugar|bs|bsl|bsg))'
            r'\s*[:\-=]?\s*([\d]+(?:\.\d+)?)\s*(?:mg/dl|mmol/l|mg%)?',

            r'(?:fbg|fbs|fpg)\s*[:\-=]?\s*([\d]+(?:\.\d+)?)',
        ],
        'glucose_random': [
            r'(?:random|post[\s\-]*prandial|rbs|pp|casual)'
            r'[\s\-]*(?:blood[\s]*)?(?:glucose|sugar|bs)\s*[:\-=]?\s*([\d]+(?:\.\d+)?)',
        ],
        'hba1c': [
            r'(?:hba1c|hb[\s]?a1[\s]?c|glycat(?:ed|ated)[\s]*hb|'
            r'glycated[\s]*hemoglobin|a1c)\s*[:\-=]?\s*([\d]+(?:\.\d+)?)\s*%?',
        ],
        'bmi': [
            r'(?:bmi|body[\s]*mass[\s]*index)\s*[:\-=]?\s*([\d]+(?:\.\d+)?)',
        ],
        'weight_kg': [
            r'(?:weight|wt\.?|wt)\s*[:\-=]?\s*([\d]+(?:\.\d+)?)\s*(?:kg|kgs|kilogram)',
            r'([\d]+(?:\.\d+)?)\s*kg\b',
        ],
        'height_cm': [
            r'(?:height|ht\.?|ht)\s*[:\-=]?\s*([\d]+(?:\.\d+)?)\s*(?:cm|cms)',
            r'([\d]+(?:\.\d+)?)\s*cm\b',
        ],
        'age': [
            r'(?:age|yr|y\.?o\.?)\s*[:\-=]?\s*(\d{1,3})\s*(?:yrs?|years?)?',
            r'(\d{1,3})\s*(?:years?[\s]*old|yr[\s]*old)',
        ],
        'blood_pressure': [
            r'(?:bp|blood[\s]*pressure|b\.p\.?)\s*[:\-=]?\s*(\d{2,3})\s*/\s*(\d{2,3})',
            r'(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mm[\s]*hg|mmhg)',
        ],
        'total_cholesterol': [
            r'(?:total[\s]*cholesterol|t\.?chol\.?|cholesterol[\s]*total)'
            r'\s*[:\-=]?\s*([\d]+(?:\.\d+)?)',
        ],
        'hdl_cholesterol': [
            r'(?:hdl[\s\-]*(?:cholesterol|chol)?|good[\s]*cholesterol)'
            r'\s*[:\-=]?\s*([\d]+(?:\.\d+)?)',
        ],
        'ldl_cholesterol': [
            r'(?:ldl[\s\-]*(?:cholesterol|chol)?|bad[\s]*cholesterol)'
            r'\s*[:\-=]?\s*([\d]+(?:\.\d+)?)',
        ],
        'triglycerides': [
            r'(?:triglycerides?|tg|trigs?)\s*[:\-=]?\s*([\d]+(?:\.\d+)?)',
        ],
        'insulin': [
            r'(?:insulin|serum[\s]*insulin)\s*[:\-=]?\s*([\d]+(?:\.\d+)?)'
            r'\s*(?:miu/ml|µiu/ml|uiu/ml)?',
        ],
        'creatinine': [
            r'(?:creatinine|s\.creat\.?)\s*[:\-=]?\s*([\d]+(?:\.\d+)?)'
            r'\s*(?:mg/dl)?',
        ],
    }

    # Range constraints for sanity checking
    VALID_RANGES = {
        'glucose_fasting':   (40,   800),
        'glucose_random':    (40,   800),
        'hba1c':             (3.0,  20.0),
        'bmi':               (10.0, 70.0),
        'weight_kg':         (5.0,  300.0),
        'height_cm':         (50.0, 250.0),
        'age':               (0,    120),
        'bp_systolic':       (60,   250),
        'bp_diastolic':      (30,   150),
        'total_cholesterol': (50,   600),
        'hdl_cholesterol':   (10,   150),
        'ldl_cholesterol':   (20,   400),
        'triglycerides':     (20,   2000),
        'insulin':           (1.0,  300.0),
        'creatinine':        (0.2,  20.0),
    }

    FAMILY_HX_POSITIVE = re.compile(
        r'(?:family[\s]*history|familial|hereditary|father|mother|parent|'
        r'sibling|brother|sister|grandfather|grandmother)\s*'
        r'(?:of\s*)?(?:diabetes|dm|t2dm|sugar)',
        re.IGNORECASE
    )
    FAMILY_HX_NEGATIVE = re.compile(
        r'no[\s]*(?:family[\s]*history|familial)[\s]*(?:of\s*)?'
        r'(?:diabetes|dm)',
        re.IGNORECASE
    )

    GENDER_MALE   = re.compile(r'\b(?:male|m\b|mr\.?|man|boy)\b', re.IGNORECASE)
    GENDER_FEMALE = re.compile(r'\b(?:female|f\b|ms\.?|mrs\.?|woman|girl)\b',
                               re.IGNORECASE)

    # mmol/L to mg/dL conversion factor for glucose
    MMOL_TO_MGDL = 18.0182

    def extract(self, raw_text: str) -> ExtractedParameters:
        """Run full extraction pipeline on OCR text."""
        params = ExtractedParameters()
        text = self._normalize_text(raw_text)

        # Numeric fields
        for field_name, patterns in self.PATTERNS.items():
            if field_name == 'blood_pressure':
                continue  # handled separately
            value = self._try_patterns(text, patterns, field_name)
            if value is not None:
                setattr(params, field_name, value)

        # Blood pressure (two capture groups)
        bp = self._extract_blood_pressure(text)
        if bp:
            params.bp_systolic, params.bp_diastolic = bp

        # Convert mmol/L glucose if value looks like it
        params.glucose_fasting = self._maybe_convert_glucose(
            params.glucose_fasting, text, 'fasting'
        )
        params.glucose_random = self._maybe_convert_glucose(
            params.glucose_random, text, 'random'
        )

        # Calculate BMI if height + weight present but BMI not extracted
        if params.bmi is None and params.weight_kg and params.height_cm:
            h_m = params.height_cm / 100
            params.bmi = round(params.weight_kg / (h_m ** 2), 1)
            params.extraction_notes.append("BMI calculated from weight/height")

        # Family history
        if self.FAMILY_HX_POSITIVE.search(text):
            params.family_hx_diabetes = 1
        elif self.FAMILY_HX_NEGATIVE.search(text):
            params.family_hx_diabetes = 0

        # Gender
        if self.GENDER_MALE.search(text) and not self.GENDER_FEMALE.search(text):
            params.gender = 1
        elif self.GENDER_FEMALE.search(text):
            params.gender = 2

        logger.info(
            f"Extracted {sum(1 for f in params.to_dict().values() if f is not None)} "
            f"parameters. Completeness: {params.completeness_score()}"
        )
        return params

    def _normalize_text(self, text: str) -> str:
        """Clean OCR artefacts before pattern matching."""
        # Lowercase for matching (keep original for display)
        text = text.lower()
        # OCR often mistakes '|' for 'I' or 'l', ':' for ';'
        text = text.replace('|', 'l').replace(';', ':')
        # Collapse multiple spaces / newlines
        text = re.sub(r'\s+', ' ', text)
        # Normalize number formats — remove commas in numbers (1,234 → 1234)
        text = re.sub(r'(\d),(\d{3})', r'\1\2', text)
        return text

    def _try_patterns(self, text: str, patterns: list,
                       field_name: str) -> Optional[float]:
        """Try each regex pattern, return first valid match."""
        lo, hi = self.VALID_RANGES.get(field_name, (0, 1e9))
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    if lo <= value <= hi:
                        return value
                except (ValueError, IndexError):
                    continue
        return None

    def _extract_blood_pressure(self, text: str):
        """Extract systolic / diastolic pair."""
        for pattern in self.PATTERNS['blood_pressure']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    sys_ = int(match.group(1))
                    dia_ = int(match.group(2))
                    sys_lo, sys_hi = self.VALID_RANGES['bp_systolic']
                    dia_lo, dia_hi = self.VALID_RANGES['bp_diastolic']
                    if (sys_lo <= sys_ <= sys_hi and
                            dia_lo <= dia_ <= dia_hi and
                            sys_ > dia_):
                        return sys_, dia_
                except (ValueError, IndexError):
                    continue
        return None

    def _maybe_convert_glucose(self, value: Optional[float],
                                text: str, label: str) -> Optional[float]:
        """Convert mmol/L glucose values to mg/dL."""
        if value is None:
            return None
        # Values < 40 are almost certainly in mmol/L (fasting glucose is 4–10 mmol/L)
        if value < 40:
            converted = round(value * self.MMOL_TO_MGDL, 1)
            logger.info(
                f"Converted {label} glucose {value} mmol/L → {converted} mg/dL"
            )
            return converted
        return value

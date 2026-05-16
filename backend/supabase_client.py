"""
Supabase Client — DiabetesSense AI
Async wrapper around supabase-py for all DB operations.
"""

import os
import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseClient:
    _client: Optional[Client] = None

    def _get_client(self) -> Client:
        if self._client is None:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")  # Use service role key server-side
            if not url or not key:
                raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
            SupabaseClient._client = create_client(url, key)
        return SupabaseClient._client

    async def save_scan(self, scan_id: str, user_id: Optional[str],
                         document_type: str, filename: str,
                         ocr_text: str, ocr_confidence: float,
                         ocr_engine: str, extracted_params: dict) -> dict:
        client = self._get_client()
        result = client.table("scans").insert({
            "id": scan_id,
            "user_id": user_id,
            "document_type": document_type,
            "filename": filename,
            "ocr_text": ocr_text,
            "ocr_confidence": ocr_confidence,
            "ocr_engine": ocr_engine,
            "extracted_params": extracted_params,
            "completeness_score": extracted_params.get("completeness_score", 0),
            "status": "complete",
        }).execute()
        return result.data[0] if result.data else {}

    async def get_scan(self, scan_id: str) -> Optional[dict]:
        client = self._get_client()
        result = client.table("scans").select("*").eq("id", scan_id).execute()
        return result.data[0] if result.data else None

    async def save_prediction(self, scan_id: Optional[str],
                               user_id: Optional[str],
                               risk_class: int, risk_level: str,
                               confidence: float, health_score: int,
                               proba: list) -> dict:
        client = self._get_client()
        result = client.table("predictions").insert({
            "scan_id": scan_id,
            "user_id": user_id,
            "risk_class": risk_class,
            "risk_level": risk_level,
            "confidence": confidence,
            "health_score": health_score,
            "diabetes_probability": round(proba[2] * 100, 1) if len(proba) > 2 else 0,
            "prediabetes_probability": round(proba[1] * 100, 1) if len(proba) > 1 else 0,
            "normal_probability": round(proba[0] * 100, 1),
        }).execute()
        return result.data[0] if result.data else {}

    async def get_user_predictions(self, user_id: str,
                                    limit: int = 10) -> list:
        client = self._get_client()
        result = (client.table("predictions")
                  .select("*")
                  .eq("user_id", user_id)
                  .order("created_at", desc=True)
                  .limit(limit)
                  .execute())
        return result.data or []

    async def award_points(self, user_id: str, points: int,
                            event_type: str, description: str = "") -> None:
        """Call the Supabase function to atomically award points + update level."""
        client = self._get_client()
        client.rpc("award_points", {
            "p_user_id": user_id,
            "p_points": points,
            "p_event": event_type,
            "p_desc": description,
        }).execute()

    async def get_leaderboard(self, limit: int = 20) -> list:
        client = self._get_client()
        result = (client.table("leaderboard")
                  .select("*")
                  .limit(limit)
                  .execute())
        return result.data or []

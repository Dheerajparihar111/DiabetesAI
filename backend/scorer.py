"""
Gamification Scorer — DiabetesSense AI
Computes level, badge eligibility, and mission progress.
"""

import math
from api.schemas import GamificationProfile, Mission, MissionStatus

LEVEL_NAMES = {
    1: "Health Starter",
    2: "Wellness Explorer",
    3: "Prevention Seeker",
    4: "Health Guardian",
    5: "Diabetes Defender",
    6: "Wellness Champion",
    7: "Prevention Master",
    8: "Health Legend",
}


def compute_level(total_points: int) -> tuple[int, str]:
    """Every 100 points = 1 level. Max level 8."""
    level = min(8, max(1, math.floor(total_points / 100) + 1))
    return level, LEVEL_NAMES.get(level, f"Level {level}")


def points_to_next_level(total_points: int) -> int:
    level = compute_level(total_points)[0]
    if level >= 8:
        return 0
    return level * 100 - total_points


def award_scan_points(risk_class: int) -> int:
    """Higher-risk scans grant more points (encourages engagement with care)."""
    return {0: 10, 1: 20, 2: 30}.get(risk_class, 10)


def award_streak_points(streak_days: int) -> int:
    """Bonus points for consecutive daily logins."""
    if streak_days >= 30:
        return 50
    elif streak_days >= 14:
        return 30
    elif streak_days >= 7:
        return 20
    elif streak_days >= 3:
        return 10
    return 0

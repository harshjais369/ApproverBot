import json
import logging
from typing import Optional, Tuple, List
from config import (
    SIMILARITY_THRESHOLD, DEVICE_ID_AUTO_FLAG,
    WEIGHT_CANVAS_HASH, WEIGHT_WEBGL_HASH,
    WEIGHT_AUDIO_HASH, WEIGHT_SCREEN,
    WEIGHT_USER_AGENT, WEIGHT_PLATFORM, WEIGHT_LANGUAGES,
    WEIGHT_TIMEZONE, WEIGHT_HARDWARE, WEIGHT_FONTS,
)

logger = logging.getLogger("approverbot")

# Components for weighted similarity scoring.
# device_id and ip_address are handled separately as fast-paths:
#   - device_id match → same Telegram app, instant flag
#   - ip_address match → same network, instant flag
# Weighted scoring uses hardware/software signals only.
COMPONENTS = [
    # (field_name, weight, comparison_type)
    ("canvas_hash",          WEIGHT_CANVAS_HASH,  "exact"),
    ("webgl_hash",           WEIGHT_WEBGL_HASH,   "exact"),
    ("audio_hash",           WEIGHT_AUDIO_HASH,   "exact"),
    ("screen_resolution",    WEIGHT_SCREEN,        "exact"),
    ("user_agent",           WEIGHT_USER_AGENT,    "exact"),
    ("platform",             WEIGHT_PLATFORM,      "exact"),
    ("languages",            WEIGHT_LANGUAGES,     "json_array_overlap"),
    ("timezone",             WEIGHT_TIMEZONE,      "exact"),
    ("hardware_concurrency", WEIGHT_HARDWARE,      "exact_int_combo"),
    ("fonts_hash",           WEIGHT_FONTS,         "exact"),
]


def _json_array_overlap(a, b) -> float:
    """Return Jaccard overlap ratio of two JSON-encoded arrays."""
    try:
        list_a = json.loads(a) if isinstance(a, str) else a
        list_b = json.loads(b) if isinstance(b, str) else b
        if not list_a or not list_b:
            return 0.0
        set_a, set_b = set(list_a), set(list_b)
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0
    except (json.JSONDecodeError, TypeError):
        return 0.0


def compare_fingerprints(new_fp: dict, existing_fp: dict) -> Tuple[float, List[str]]:
    """
    Compare two fingerprint dicts using weighted component scoring.
    device_id and ip_address are excluded (handled as separate fast-paths).
    Returns (similarity_score, list_of_matching_component_names).
    """
    total_score = 0.0
    total_weight = 0.0
    matched_components = []

    for field_name, weight, comparison_type in COMPONENTS:
        new_val = new_fp.get(field_name)
        existing_val = existing_fp.get(field_name)

        # Skip if either value is missing/empty
        if not new_val and new_val != 0:
            continue
        if not existing_val and existing_val != 0:
            continue

        total_weight += weight
        match = False

        if comparison_type == "exact":
            match = str(new_val).strip() == str(existing_val).strip()

        elif comparison_type == "json_array_overlap":
            match = _json_array_overlap(new_val, existing_val) >= 0.8

        elif comparison_type == "exact_int_combo":
            # hardware_concurrency + device_memory combined check
            match = (
                str(new_val).strip() == str(existing_val).strip()
                and str(new_fp.get("device_memory", "")).strip()
                    == str(existing_fp.get("device_memory", "")).strip()
            )

        if match:
            total_score += weight
            matched_components.append(field_name)

    if total_weight == 0:
        return 0.0, []

    normalized_score = total_score / total_weight
    return normalized_score, matched_components


def find_matching_user(
    new_fp: dict, all_existing: list
) -> Optional[Tuple[dict, float, List[str]]]:
    """
    Compare new_fp against all existing fingerprints.
    Returns the best match above threshold, or None.
    """
    best_match = None
    best_score = 0.0
    best_components: List[str] = []

    for existing_fp in all_existing:
        score, components = compare_fingerprints(new_fp, existing_fp)

        logger.debug(
            "Fingerprint comparison: user %s vs user %s -> %.0f%% (%s)",
            new_fp.get("user_id", "?"),
            existing_fp.get("user_id", "?"),
            score * 100,
            ", ".join(components) if components else "none",
        )

        if score > best_score:
            best_score = score
            best_match = existing_fp
            best_components = components

    if best_score >= SIMILARITY_THRESHOLD and best_match is not None:
        logger.info(
            "Match found: user %s matches user %s at %.0f%% (%s)",
            new_fp.get("user_id", "?"),
            best_match.get("user_id", "?"),
            best_score * 100,
            ", ".join(best_components),
        )
        return (best_match, best_score, best_components)

    if best_match:
        logger.info(
            "Best match for user %s was user %s at %.0f%% (below %.0f%% threshold)",
            new_fp.get("user_id", "?"),
            best_match.get("user_id", "?"),
            best_score * 100,
            SIMILARITY_THRESHOLD * 100,
        )

    return None


def check_device_id_match(device_id: str, exclude_user_id: int, db_module) -> Optional[dict]:
    """
    Fast-path #1: localStorage device_id matches another user.
    Same Telegram app, different account.
    """
    if not device_id or not DEVICE_ID_AUTO_FLAG:
        return None
    return db_module.find_by_device_id(device_id, exclude_user_id)


def check_ip_match(ip_address: str, exclude_user_id: int, db_module) -> Optional[dict]:
    """
    Fast-path #2: IP address matches another user.
    Same network = same user.
    """
    if not ip_address:
        return None
    return db_module.find_by_ip(ip_address, exclude_user_id)

import json
from typing import Optional, Tuple, List
from config import (
    SIMILARITY_THRESHOLD, DEVICE_ID_AUTO_FLAG,
    WEIGHT_DEVICE_ID, WEIGHT_CANVAS_HASH, WEIGHT_WEBGL_HASH,
    WEIGHT_AUDIO_HASH, WEIGHT_IP_ADDRESS, WEIGHT_SCREEN,
    WEIGHT_USER_AGENT, WEIGHT_PLATFORM, WEIGHT_LANGUAGES,
    WEIGHT_TIMEZONE, WEIGHT_HARDWARE, WEIGHT_FONTS,
)

# (field_name, weight, comparison_type)
COMPONENTS = [
    ("device_id",            WEIGHT_DEVICE_ID,    "exact"),
    ("canvas_hash",          WEIGHT_CANVAS_HASH,  "exact"),
    ("webgl_hash",           WEIGHT_WEBGL_HASH,   "exact"),
    ("audio_hash",           WEIGHT_AUDIO_HASH,   "exact"),
    ("ip_address",           WEIGHT_IP_ADDRESS,    "exact"),
    ("screen_resolution",    WEIGHT_SCREEN,        "exact"),
    ("user_agent",           WEIGHT_USER_AGENT,    "exact"),
    ("platform",             WEIGHT_PLATFORM,      "exact"),
    ("languages",            WEIGHT_LANGUAGES,     "json_array_overlap"),
    ("timezone",             WEIGHT_TIMEZONE,      "exact"),
    ("hardware_concurrency", WEIGHT_HARDWARE,      "exact_int_combo"),
    ("fonts_hash",           WEIGHT_FONTS,         "exact"),
]


def _json_array_overlap(a, b) -> float:
    """Return overlap ratio of two JSON-encoded arrays."""
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
                new_val == existing_val
                and new_fp.get("device_memory") == existing_fp.get("device_memory")
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
        if score > best_score:
            best_score = score
            best_match = existing_fp
            best_components = components

    if best_score >= SIMILARITY_THRESHOLD and best_match is not None:
        return (best_match, best_score, best_components)

    return None


def check_device_id_match(device_id: str, exclude_user_id: int, db_module) -> Optional[dict]:
    """
    Fast-path: if localStorage device_id exactly matches another user,
    that's near-certain multi-account evidence.
    """
    if not device_id or not DEVICE_ID_AUTO_FLAG:
        return None
    return db_module.find_by_device_id(device_id, exclude_user_id)

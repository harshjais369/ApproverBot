import json
import logging
from typing import Optional, Tuple, List
import requests
from config import (
    SIMILARITY_THRESHOLD, DEVICE_ID_AUTO_FLAG,
    WEIGHT_CANVAS_HASH, WEIGHT_WEBGL_HASH,
    WEIGHT_AUDIO_HASH, WEIGHT_SCREEN,
    WEIGHT_USER_AGENT, WEIGHT_PLATFORM, WEIGHT_LANGUAGES,
    WEIGHT_TIMEZONE, WEIGHT_HARDWARE, WEIGHT_FONTS, WEIGHT_IP_INFO,
)

logger = logging.getLogger("approverbot")

def fetch_ip_geolocation(ip_address: str, timeout: int = 3) -> Optional[dict]:
    """
    Fetch IP geolocation data from ip-api.com.
    Args:
        ip_address: IPv4 or IPv6 address to look up
        timeout: Request timeout in seconds (default 3)
    Returns:
        Dict with keys: {"isp": "...", "location": "...", "mobile": bool}
        or None if request fails, times out, or API returns error
    """
    if not ip_address: return None
    try:
        url = f"http://ip-api.com/json/{ip_address}?fields=status,message,country," \
            "countryCode,region,regionName,city,district,zip,lat,lon,timezone,isp,org,as,asname,mobile,hosting,query"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            city = data.get("city", "").strip()
            region = data.get("regionName", "").strip()
            country = data.get("country", "").strip()
            location_parts = [p for p in [city, region, country] if p]
            location = ", ".join(location_parts) if location_parts else ""
            return {
                "isp": data.get("isp", "").strip(),
                "location": location,
                "mobile": bool(data.get("mobile", False))
            }
        else:
            logger.info("IP geolocation API returned error for %s: %s", ip_address, data.get("message", "unknown"))
    except requests.exceptions.Timeout:
        logger.warning("IP geolocation request timed out for %s (timeout=%ds)", ip_address, timeout)
    except requests.exceptions.RequestException as e:
        logger.warning("IP geolocation request failed for %s: %s", ip_address, str(e))
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse IP geolocation response for %s: %s", ip_address, str(e))
    except Exception as e:
        logger.warning("Unexpected error fetching IP geolocation for %s: %s", ip_address, str(e))
    return None

def _compare_ip_info(ip_info_a, ip_info_b) -> bool:
    """
    Compare two ip_info JSON objects for exact match.
    Both ISP, location, and mobile status must match exactly.
    """
    if not ip_info_a or not ip_info_b:
        return False
    try:
        data_a = json.loads(ip_info_a) if isinstance(ip_info_a, str) else ip_info_a
        data_b = json.loads(ip_info_b) if isinstance(ip_info_b, str) else ip_info_b
        return (
            data_a.get("isp") == data_b.get("isp")
            and data_a.get("location") == data_b.get("location")
            and data_a.get("mobile") == data_b.get("mobile")
        )
    except (json.JSONDecodeError, TypeError):
        return False

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
    ("ip_info",              WEIGHT_IP_INFO,       "json_object_exact"),
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
                and str(new_fp.get("device_memory", "")).strip() == str(existing_fp.get("device_memory", "")).strip()
            )
        elif comparison_type == "json_object_exact":
            # ip_info: exact match on all 3 fields (isp, location, mobile)
            match = _compare_ip_info(new_val, existing_val)
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
        logger.info(
            "Match found: user %s matches user %s at %.0f%% (%s)",
            new_fp.get("user_id", "?"),
            best_match.get("user_id", "?"),
            best_score * 100,
            ", ".join(best_components),
        )
        return (best_match, best_score, best_components)
    if best_match:
        logger.info("Best match for user %s was user %s at %.0f%% (below %.0f%% threshold)",
            new_fp.get("user_id", "?"), best_match.get("user_id", "?"), best_score * 100, SIMILARITY_THRESHOLD * 100,)
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

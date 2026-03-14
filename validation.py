import hmac
import hashlib
import json
import logging
from urllib.parse import unquote
from config import BOT_TOKEN

logger = logging.getLogger("approverbot")


def validate_init_data(init_data_raw: str) -> dict | None:
    """
    Validate Telegram Mini Web App initData using HMAC-SHA256.

    Per Telegram docs, only 'hash' is excluded from the data-check-string.
    All other fields (including 'signature') remain.
    """
    if not init_data_raw:
        return None

    # Parse into {key: value} pairs — keep values as-is from the query string
    pairs = {}
    for part in init_data_raw.split("&"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        pairs[key] = value

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        logger.warning("No hash field in initData")
        return None

    # Build data_check_string: sorted by key, joined by \n, using URL-decoded values
    sorted_keys = sorted(pairs.keys())
    data_check_string = "\n".join(
        f"{k}={unquote(pairs[k])}" for k in sorted_keys
    )

    # secret_key = HMAC-SHA256(key="WebAppData", msg=bot_token)
    secret_key = hmac.new(
        key="WebAppData".encode("utf-8"),
        msg=BOT_TOKEN.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    # computed_hash = hex(HMAC-SHA256(key=secret_key, msg=data_check_string))
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        # Debug: log to help diagnose
        logger.debug("initData raw (first 200): %s", init_data_raw[:200])
        logger.debug("data_check_string (first 300): %s", data_check_string[:300])
        logger.debug("computed: %s", computed_hash)
        logger.debug("received: %s", received_hash)

        # Retry with raw (non-decoded) values in case Telegram uses encoded form
        data_check_string_raw = "\n".join(
            f"{k}={pairs[k]}" for k in sorted_keys
        )
        computed_hash_raw = hmac.new(
            key=secret_key,
            msg=data_check_string_raw.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if hmac.compare_digest(computed_hash_raw, received_hash):
            # Raw (encoded) form matched
            decoded = {k: unquote(v) for k, v in pairs.items()}
            return decoded

        logger.warning("initData HMAC mismatch (both decoded and raw tried)")
        logger.warning("Keys present: %s", list(pairs.keys()))
        return None

    # Decode values for downstream use
    decoded = {k: unquote(v) for k, v in pairs.items()}
    return decoded


def extract_user_id(validated_data: dict) -> int | None:
    """Extract user ID from validated initData."""
    user_json = validated_data.get("user", "{}")
    try:
        user = json.loads(user_json)
        uid = user.get("id")
        return int(uid) if uid is not None else None
    except (json.JSONDecodeError, ValueError, TypeError):
        return None

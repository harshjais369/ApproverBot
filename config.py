import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0"))  # Chat where alerts are sent
LOG_THREAD_ID = int(os.getenv("LOG_THREAD_ID", "0"))  # Thread in log chat for alerts (0 = no thread)
SUPERUSERS = [
    int(uid.strip())
    for uid in os.getenv("SUPERUSERS", "").split(",")
    if uid.strip()
]  # User IDs that can execute commands in any chat
ALLOWED_GROUPS = [
    int(gid.strip())
    for gid in os.getenv("ALLOWED_GROUPS", "").split(",")
    if gid.strip()
]  # Only process join requests from these groups (empty = all groups)

# Web server
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8443"))
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "")  # e.g. "https://yourdomain.com"

# Database
DB_PATH = os.getenv("DB_PATH", "approverbot.db")

# Fingerprint matching
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))
DEVICE_ID_AUTO_FLAG = os.getenv("DEVICE_ID_AUTO_FLAG", "true").lower() == "true"
AUTO_DECLINE_ON_MATCH = os.getenv("AUTO_DECLINE_ON_MATCH", "false").lower() == "true"
PENDING_REQUEST_TTL_MINUTES = int(os.getenv("PENDING_REQUEST_TTL_MINUTES", "30"))

# Fingerprint component weights (sum = 1.0)
# device_id and ip_address are handled as separate fast-paths, not in weighted scoring
WEIGHT_CANVAS_HASH = float(os.getenv("WEIGHT_CANVAS_HASH", "0.20"))
WEIGHT_FONTS = float(os.getenv("WEIGHT_FONTS", "0.20"))
WEIGHT_USER_AGENT = float(os.getenv("WEIGHT_USER_AGENT", "0.18"))
WEIGHT_AUDIO_HASH = float(os.getenv("WEIGHT_AUDIO_HASH", "0.15"))
WEIGHT_WEBGL_HASH = float(os.getenv("WEIGHT_WEBGL_HASH", "0.08"))
WEIGHT_HARDWARE = float(os.getenv("WEIGHT_HARDWARE", "0.05"))
WEIGHT_SCREEN = float(os.getenv("WEIGHT_SCREEN", "0.05"))
WEIGHT_PLATFORM = float(os.getenv("WEIGHT_PLATFORM", "0.04"))
WEIGHT_TIMEZONE = float(os.getenv("WEIGHT_TIMEZONE", "0.04"))
WEIGHT_LANGUAGES = float(os.getenv("WEIGHT_LANGUAGES", "0.01"))

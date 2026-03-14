import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

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
WEIGHT_DEVICE_ID = float(os.getenv("WEIGHT_DEVICE_ID", "0.30"))
WEIGHT_CANVAS_HASH = float(os.getenv("WEIGHT_CANVAS_HASH", "0.15"))
WEIGHT_WEBGL_HASH = float(os.getenv("WEIGHT_WEBGL_HASH", "0.10"))
WEIGHT_AUDIO_HASH = float(os.getenv("WEIGHT_AUDIO_HASH", "0.10"))
WEIGHT_IP_ADDRESS = float(os.getenv("WEIGHT_IP_ADDRESS", "0.10"))
WEIGHT_SCREEN = float(os.getenv("WEIGHT_SCREEN", "0.05"))
WEIGHT_USER_AGENT = float(os.getenv("WEIGHT_USER_AGENT", "0.05"))
WEIGHT_PLATFORM = float(os.getenv("WEIGHT_PLATFORM", "0.03"))
WEIGHT_LANGUAGES = float(os.getenv("WEIGHT_LANGUAGES", "0.03"))
WEIGHT_TIMEZONE = float(os.getenv("WEIGHT_TIMEZONE", "0.03"))
WEIGHT_HARDWARE = float(os.getenv("WEIGHT_HARDWARE", "0.03"))
WEIGHT_FONTS = float(os.getenv("WEIGHT_FONTS", "0.03"))

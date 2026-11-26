"""Sozlamalar. Barcha maxfiy qiymatlar muhit o'zgaruvchilaridan olinadi (kodda token YO'Q)."""
import os
import pytz

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def _load_dotenv(path):
    """Mahalliy ishlab chiqish uchun oddiy .env o'qigich (qo'shimcha kutubxonasiz)."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(BASE_DIR, ".env"))


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("BOT_TOKEN") or ""
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

ADMIN_ID = _int("ADMIN_ID", 5423849679)
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@onatilidanyordam")
CHANNEL_URL = os.environ.get("CHANNEL_URL", "https://t.me/onatilidanyordam")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "aitilshunosbot")

PUBLIC_URL = (
    os.environ.get("PUBLIC_URL")
    or os.environ.get("RENDER_EXTERNAL_URL")
    or "https://aitilshunosbot.onrender.com"
).rstrip("/")
PORT = _int("PORT", 8080)

# Gemini modellari (vergul bilan). Eskirgan model bo'lsa, keyingisiga o'tadi.
GEMINI_MODELS = [
    m.strip()
    for m in os.environ.get("GEMINI_MODELS", "gemini-2.5-flash,gemini-2.5-flash-lite").split(",")
    if m.strip()
]

# AI foydalanish chegaralari (serverni va kvotani himoyalash)
AI_COOLDOWN_SEC = _int("AI_COOLDOWN_SEC", 4)
AI_DAILY_LIMIT = _int("AI_DAILY_LIMIT", 60)

# Guruh bellashuvi
MIN_PLAYERS = _int("MIN_PLAYERS", 2)          # test shuncha kishi «Tayyorman»ni bosgach boshlanadi
LOBBY_TTL_SEC = 15 * 60                       # guruh lobbisi ochiq turadigan vaqt
QUIZ_PAUSE_MAX_MIN = _int("QUIZ_PAUSE_MAX_MIN", 60)  # pauzada eng ko'p kutish (daqiqa), so'ng test yakunlanadi
LAST_LOBBY_MIN = _int("LAST_LOBBY_MIN", 60)   # kunning oxirgi kanal testi lobbisi necha daqiqa ochiq

TZ = pytz.timezone(os.environ.get("BOT_TZ", "Asia/Tashkent"))
NUM_THREADS = _int("NUM_THREADS", 16)

BOT_VERSION = "v12.2"

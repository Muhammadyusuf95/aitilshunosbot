"""Mavzu filtri (diniy/siyosiy/huquqiy/tibbiy/haqoratli so'rovlar) va AI so'rovlar limiti.

Eski versiyada filtr oddiy `kw in text` edi: "din" so'zi "maqsadini", "yodingiz" ichida,
"oyat" esa "hikoyat", "rivoyat" ichida topilib, oddiy adabiy so'rovlar ham bloklanardi.
Endi moslik SO'Z BOSHIDAN tekshiriladi, qisqa/noaniq so'zlar esa faqat to'liq so'z (+ odatiy qo'shimcha) sifatida.
"""
import re
import threading
import time

from app import config

_APOS = re.compile(r"[ʻʼ‘’`´′]")

# Uzun, noaniqlik tug'dirmaydigan o'zaklar — so'z boshidan moslik yetarli
_PREFIX = [
    "prezident", "mirziyoyev", "siyosat", "saylov", "muxolifat", "deputat", "amaldor", "hukumat",
    "hokimiyat", "hokimlik", "shariat", "masjid", "xristian", "cherkov", "yahudiy", "fatvo", "namoz",
    "ro'za", "islom", "qur'on", "prokuror", "advokat", "qamoq", "tibbiyot", "davolash", "kasallik",
    "tashxis", "shifokor", "retsept", "ekstremizm", "terrorizm", "jihod", "vahobiy", "inqilob",
    "portlash", "ahmoq", "tentak", "haromi", "kofir", "fahisha", "fosiq", "iflos", "partiya",
]
# Qisqa/noaniq so'zlar — faqat to'liq so'z yoki oddiy qo'shimchalar bilan
_STRICT = ["din", "sud", "dori", "modda", "oyat", "hadis", "imom", "mulla", "hizb", "hokim", "vazir",
           "qurol", "padar", "jalab", "taqvo"]
_SUFFIX = r"(?:lar|ni|ning|ga|da|dan|i|si|ini|ing|imiz|lik|ligi|iy|chi|ya|xona|ham|li|siz)*"
_PHRASES = ["davlat boshqaruvi", "jinoyat kodeksi"]

_RE_PREFIX = re.compile(r"(?<![a-zо-я])(?:" + "|".join(re.escape(w) for w in _PREFIX) + ")", re.I)
_RE_STRICT = re.compile(r"(?<![a-zо-я'])(?:" + "|".join(_STRICT) + ")" + _SUFFIX + r"(?![a-zо-я'])", re.I)


def _normalize(text):
    return _APOS.sub("'", (text or "").lower())


def check_security_violation(text):
    """True — matn bot yo'nalishiga to'g'ri kelmaydigan mavzularni o'z ichiga oladi."""
    if not text:
        return False
    t = _normalize(text)
    if any(p in t for p in _PHRASES):
        return True
    return bool(_RE_PREFIX.search(t) or _RE_STRICT.search(t))


SECURITY_WARNING = (
    "⚠️ <b>Mavzu doirasidan tashqari so'rov</b>\n\n"
    "Bot faqat <b>ona tili, adabiyot va dars metodikasi</b> yo'nalishida xizmat ko'rsatadi.\n"
    "<blockquote>Diniy, siyosiy, huquqiy, tibbiy mavzular hamda haqoratli yoki buzg'unchilik mazmunidagi "
    "so'rovlar qabul qilinmaydi.</blockquote>\n"
    "Iltimos, so'rovingizni til yoki adabiyotga oid qilib qayta yozing."
)


class RateLimiter:
    """Foydalanuvchi uchun AI chaqiruvlarini cheklaydi: oraliq (cooldown) + kunlik limit."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last = {}
        self._day = {}

    def check(self, uid, today):
        """(ruxsat, sabab) qaytaradi. Admin cheklanmaydi."""
        if uid == config.ADMIN_ID:
            return True, ""
        now = time.time()
        with self._lock:
            last = self._last.get(uid, 0)
            wait = config.AI_COOLDOWN_SEC - (now - last)
            if wait > 0:
                return False, f"⏳ Iltimos, {int(wait) + 1} soniya kuting."
            day, cnt = self._day.get(uid, (today, 0))
            if day != today:
                day, cnt = today, 0
            if cnt >= config.AI_DAILY_LIMIT:
                return False, (f"📊 Bugungi AI so'rovlar limiti ({config.AI_DAILY_LIMIT} ta) tugadi. "
                               "Ertaga yana urinib ko'ring — mashq rejimlari esa cheklanmagan!")
            self._last[uid] = now
            self._day[uid] = (day, cnt + 1)
            return True, ""

    def used_today(self, uid, today):
        day, cnt = self._day.get(uid, (today, 0))
        return cnt if day == today else 0


limiter = RateLimiter()

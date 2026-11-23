"""Mavzu va axloq filtri — ko'p qatlamli himoya.

Bot FAQAT tilshunoslik, ona tili, adabiyot va filologik ilmiy tadqiqot yo'nalishida xizmat qiladi.

Qatlamlar:
 1. Kirish filtri (kalit so'z + kontekst): diniy, siyosiy, ekstremizm, davlat/rahbar/amaldorlarni maqtash yoki
    tanqid qilish, tuzum va qonunchilikni tanqid, oqimlar, haqorat, behayo mazmun, boshqa sohalar (tibbiyot, huquq).
    Kirill yozuvidagi matn avval lotinga o'giriladi.
 2. AI tizim ko'rsatmasi: mavzudan tashqari so'rovga "OFFTOPIC_REFUSED" qaytaradi (ai.py).
 3. Chiqish filtri: AI javobidagi qat'iy taqiqlangan mazmun (haqorat, behayo, ekstremizm) yuborilmaydi.
 4. Ogohlantirish tizimi: 24 soat ichida 3 marta qoidabuzarlik — 24 soatga AI xizmatlaridan chetlatish, admin xabardor qilinadi.

Moslik SO'Z BOSHIDAN tekshiriladi ("hikoyat" ichidagi "oyat" yoki "maqsadini" ichidagi "din" tutilmaydi).
"""
import re
import threading
import time

from app import config
from app.translit import cyrillic_to_latin

_APOS = re.compile(r"[ʻʼ‘’`´′]")
_CYR = re.compile(r"[а-яёўқғҳ]", re.I)

# ---- Uzun o'zaklar: so'z boshidan moslik yetarli ----
_PREFIX_POLITICS = [
    "prezident", "mirziyoyev", "karimov", "siyosat", "siyosiy", "saylov", "muxolifat", "deputat", "amaldor",
    "mansabdor", "hukumat", "hokimiyat", "hokimlik", "parlament", "senat", "oliy majlis", "vazirlar mahkamasi",
    "konstitutsiya", "qonunchilik", "davlat boshqaruvi", "davlat tuzumi", "tuzum", "rejim", "rahbariyat",
    "davlat rahbari", "mitingi", "miting", "norozilik", "namoyish", "inqilob", "to'ntarish", "korrupsiya",
    "poraxo'r", "partiya", "sanksiya", 
]
_PREFIX_RELIGION = [
    "shariat", "masjid", "xristian", "cherkov", "yahudiy", "fatvo", "namoz", "ro'za", "islom", "qur'on", "alloh",
    "payg'ambar", "tafsir", "mazhab", "tariqat", "aqida", "bid'at", "salafiy", "bibliya", "injil", "tavrot",
    "ibodat", "vahiy", "diniy", "ateizm", "xalifalik", "takfir",
    "sekta", "missioner", "evangel", "buddizm", "hinduizm", "zardushtiy", "ibodatxona",
]
_PREFIX_EXTREMISM = [
    "ekstrem", "terror", "jihod", "vahobiy", "radikal", "mutaassib", "jangari", "separatist", "portlash",
    "portlat", "qotillik", "o'ldirish", "qurollan", "isis", "alqoida", "taliban", "hizbut", "hizb ut", "akromiy",
    "tashviqot", "bo'lginchi",
]
_PREFIX_INSULT = [
    "haqorat", "kamsit", "so'kin", "so'kish", "ahmoq", "tentak", "haromi", "kofir", "fosiq", "iflos", "la'nat",
    "pastkash", "yaramas", "qo'rqoq it", "mahmadana", "nodon odam", "tubanlik",
]
_PREFIX_OBSCENE = [
    "porno", "erotik", "jinsiy", "yalang'och", "yalangoch", "behayo", "fahsh", "fohisha", "intim", "seksual",
    "xxx", "nudes", "18+", "o'smir jinsiy", "qahba", "dalbayop", "siktir", "blya", "xuy", "pizd", "ebat",
]
_PREFIX_OTHER_FIELDS = [
    "tibbiyot", "davolash", "kasallik", "tashxis", "shifokor", "retsept", "prokuror", "advokat", "qamoq",
    "sudlanuvchi", "da'vogar", "jinoyat kodeksi", "kriptovalyuta", "bitkoin", "birja", "investitsiya",
    "fors-major", "soliq", "valyuta kursi", "gadjet narxi", "futbol", "bukmeker", "garov o'yin", "kazino",
    "retsept", "dori-darmon", "narkotik", "giyohvand",
]
# ---- Qisqa/noaniq so'zlar: faqat to'liq so'z (+ odatiy qo'shimcha) ----
_STRICT = ["din", "sud", "dori", "modda", "oyat", "hadis", "imom", "mulla", "hizb", "hokim", "vazir", "qurol",
           "padar", "jalab", "taqvo", "xudo", "sik", "kot", "suka", "shayton", "gunoh", "savob",
           "milliy g'oya", "xalq dushmani"]
_SUFFIX = r"(?:lar|ni|ning|ga|da|dan|i|si|ini|ing|imiz|lik|ligi|iy|chi|ya|xona|ham|li|siz|ka|ga)*"

# Davlat/qonun konteksti + tanqid/maqtov belgisi birga kelsa — taqiqlanadi
_GOV_CTX = ["davlat", "hukumat", "qonun", "rahbar", "tuzum", "mamlakat", "prezident", "vazir", "amaldor", "hokim",
            "o'zbekiston rahbar", "idora", "mansab"]
_CRITIC_PRAISE = ["tanqid", "qoral", "ayblash", "ayblov", "zolim", "mustabid", "diktator", "noqonuniy", "adolatsiz",
                  "yomon", "buzilgan", "kamchilik", "maqtov", "maqta", "ulug'la", "ulug'lash", "madh etish",
                  "sharaflash", "ta'rifla", "tahsin", "e'tiroz", "isyon", "qarshi chiq", "ag'dar", "norozi",
                  "zulm", "shafqatsiz", "firibgar", "o'g'ri"]

_PHRASES = ["davlat boshqaruvi", "jinoyat kodeksi", "milliy g'oya"]


def _words(lst):
    return "|".join(re.escape(w) for w in sorted(set(lst), key=len, reverse=True))


_ALL_PREFIX = (_PREFIX_POLITICS + _PREFIX_RELIGION + _PREFIX_EXTREMISM + _PREFIX_INSULT + _PREFIX_OBSCENE
               + _PREFIX_OTHER_FIELDS)
_HARD_PREFIX = _PREFIX_EXTREMISM + _PREFIX_INSULT + _PREFIX_OBSCENE

_RE_PREFIX = re.compile(r"(?<![a-z])(?:" + _words(_ALL_PREFIX) + ")", re.I)
_RE_HARD = re.compile(r"(?<![a-z])(?:" + _words(_HARD_PREFIX) + ")", re.I)
_RE_STRICT = re.compile(r"(?<![a-z'])(?:" + _words(_STRICT) + ")" + _SUFFIX + r"(?![a-z'])", re.I)
_RE_GOV = re.compile(r"(?<![a-z])(?:" + _words(_GOV_CTX) + ")", re.I)
_RE_CRIT = re.compile(r"(?<![a-z])(?:" + _words(_CRITIC_PRAISE) + ")", re.I)


def _normalize(text):
    t = (text or "").lower()
    if _CYR.search(t):
        t = cyrillic_to_latin(t).lower()
    t = _APOS.sub("'", t)
    return t


def check_security_violation(text):
    """True — matn bot yo'nalishiga to'g'ri kelmaydi (kirish filtri)."""
    if not text:
        return False
    t = _normalize(text)
    if any(p in t for p in _PHRASES):
        return True
    if _RE_PREFIX.search(t) or _RE_STRICT.search(t):
        return True
    return bool(_RE_GOV.search(t) and _RE_CRIT.search(t))


def check_hard_violation(text):
    """Chiqish filtri: AI javobi yoki savolida qat'iy taqiqlangan mazmun (haqorat, behayo, ekstremizm)."""
    if not text:
        return False
    return bool(_RE_HARD.search(_normalize(text)))


SECURITY_WARNING = (
    "⚠️ <b>So'rov qabul qilinmadi</b>\n\n"
    "Bot faqat <b>tilshunoslik, ona tili, adabiyot va filologik ilmiy tadqiqot</b> yo'nalishida xizmat ko'rsatadi.\n"
    "<blockquote>Diniy, siyosiy, ekstremistik mazmundagi, davlat, rahbar va amaldorlarni maqtash yoki tanqid qilish, "
    "tuzum va qonunchilikni muhokama qilish, turli oqimlarga oid, shaxs qadr-qimmatini kamsituvchi, behayo hamda "
    "boshqa sohalarga oid so'rovlar qat'iyan taqiqlanadi.</blockquote>\n"
    "Iltimos, so'rovingizni til yoki adabiyotga oid qilib qayta yozing."
)

BLOCKED_TEXT = (
    "⛔ <b>Qoidabuzarlik sababli AI xizmatlari 24 soatga cheklandi.</b>\n"
    "Bot faqat til va adabiyot yo'nalishida ishlaydi. Mashq va testlar (AI'siz) ishlashda davom etadi."
)


class Strikes:
    """24 soat ichida takroriy qoidabuzarlik uchun vaqtinchalik cheklov."""
    LIMIT = 3
    WINDOW = 24 * 3600

    def __init__(self):
        self._lock = threading.Lock()
        self._hits = {}
        self._blocked = {}

    def add(self, uid):
        """Qoidabuzarlikni qayd etadi. Qaytaradi: (soni, endi bloklandimi)."""
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(uid, []) if now - t < self.WINDOW] + [now]
            self._hits[uid] = hits
            if len(hits) >= self.LIMIT and uid != config.ADMIN_ID:
                self._blocked[uid] = now + self.WINDOW
                self._hits[uid] = []
                return len(hits), True
            return len(hits), False

    def is_blocked(self, uid):
        if uid == config.ADMIN_ID:
            return False
        with self._lock:
            until = self._blocked.get(uid, 0)
            if until and until < time.time():
                self._blocked.pop(uid, None)
                return False
            return bool(until)

    def unblock(self, uid):
        with self._lock:
            self._blocked.pop(uid, None)
            self._hits.pop(uid, None)


strikes = Strikes()


class RateLimiter:
    """AI chaqiruvlari: oraliq (cooldown) + kunlik limit."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last = {}
        self._day = {}

    def check(self, uid, today):
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

"""Alifbo konvertori: Lotin <-> Yangi lotin (Ö Ğ Ş Ç) va Kirill <-> Lotin."""
import re

_APOS = "ʻʼ‘’`´′"
_APOS_RE = re.compile(f"[{re.escape(_APOS)}]")

# ---------------- Lotin -> Yangi alifbo (Ö, Ğ, Ş, Ç) ----------------
_TO_NEW = [
    ("O'", "Ö"), ("o'", "ö"), ("G'", "Ğ"), ("g'", "ğ"),
    ("SH", "Ş"), ("Sh", "Ş"), ("sH", "ş"), ("sh", "ş"),
    ("CH", "Ç"), ("Ch", "Ç"), ("cH", "ç"), ("ch", "ç"),
]


def latin_to_new(text):
    if not text:
        return ""
    t = _APOS_RE.sub("'", text)
    for old, new in _TO_NEW:
        t = t.replace(old, new)
    return t


def new_to_latin(text):
    if not text:
        return ""
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        nxt = text[i + 1] if i + 1 < n else ""
        prv = text[i - 1] if i > 0 else ""
        caps_ctx = nxt.isupper() or prv.isupper()
        if ch == "Ö":
            out.append("O'")
        elif ch == "ö":
            out.append("o'")
        elif ch == "Ğ":
            out.append("G'")
        elif ch == "ğ":
            out.append("g'")
        elif ch == "Ş":
            out.append("SH" if caps_ctx else "Sh")
        elif ch == "ş":
            out.append("sh")
        elif ch == "Ç":
            out.append("CH" if caps_ctx else "Ch")
        elif ch == "ç":
            out.append("ch")
        else:
            out.append(ch)
    return "".join(out)


# ---------------- Kirill -> Lotin ----------------
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ч": "ch", "ш": "sh", "э": "e", "ю": "yu", "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'",
    "ҳ": "h", "ё": "yo", "ц": "ts", "ъ": "'", "ь": "", "щ": "shch", "ы": "i",
}
_CYR_VOWELS = set("аоуиэеёюяўыъь")


def cyrillic_to_latin(text):
    if not text:
        return ""
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        low = ch.lower()
        if low == "е":
            prev = text[i - 1].lower() if i > 0 else ""
            lat = "ye" if (i == 0 or not prev.isalpha() or prev in _CYR_VOWELS) else "e"
        elif low in _CYR:
            lat = _CYR[low]
        else:
            out.append(ch)
            continue
        if ch.isupper() and lat:
            nxt = text[i + 1] if i + 1 < n else ""
            lat = lat.upper() if (len(lat) > 1 and nxt.isupper()) else lat[0].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


# ---------------- Lotin -> Kirill ----------------
_LAT = {
    "a": "а", "b": "б", "d": "д", "f": "ф", "g": "г", "h": "ҳ", "i": "и", "j": "ж", "k": "к", "l": "л",
    "m": "м", "n": "н", "o": "о", "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "x": "х", "y": "й", "z": "з", "c": "с", "w": "в",
}
_LAT_VOWELS = set("aeiou")


def latin_to_cyrillic(text):
    if not text:
        return ""
    t = _APOS_RE.sub("'", text)
    out = []
    i, n = 0, len(t)

    def cased(src, cyr):
        return cyr.upper() if src.isupper() else cyr

    while i < n:
        ch = t[i]
        low = ch.lower()
        two = t[i:i + 2].lower()
        prev = t[i - 1].lower() if i > 0 else ""
        word_start = (i == 0) or not (t[i - 1].isalpha() or t[i - 1] == "'")
        nxt_up = i + 2 < n and t[i + 2].isupper()

        if two == "o'":
            out.append(cased(ch, "ў")); i += 2; continue
        if two == "g'":
            out.append(cased(ch, "ғ")); i += 2; continue
        if two == "sh":
            out.append("Ш" if ch.isupper() else "ш"); i += 2; continue
        if two == "ch":
            out.append("Ч" if ch.isupper() else "ч"); i += 2; continue
        if two == "yo":
            out.append(cased(ch, "ё")); i += 2; continue
        if two == "yu":
            out.append(cased(ch, "ю")); i += 2; continue
        if two == "ya":
            out.append(cased(ch, "я")); i += 2; continue
        if two == "ye":
            out.append(cased(ch, "е")); i += 2; continue
        if two == "ts" and word_start:
            out.append(cased(ch, "ц")); i += 2; continue
        if low == "e":
            out.append(cased(ch, "э" if (word_start or prev in _LAT_VOWELS) else "е")); i += 1; continue
        if ch == "'":
            out.append("ъ" if (i > 0 and t[i - 1].isalpha() and i + 1 < n and t[i + 1].isalpha()) else "'")
            i += 1; continue
        if low in _LAT:
            out.append(cased(ch, _LAT[low])); i += 1; continue
        out.append(ch)
        i += 1
    return "".join(out)


# ---------------- Yagona kirish nuqtasi ----------------
MODES = {
    "lat2new": ("Lotin → Yangi alifbo (Ö Ğ Ş Ç)", latin_to_new),
    "new2lat": ("Yangi alifbo → Lotin", new_to_latin),
    "cyr2lat": ("Kirill → Lotin", cyrillic_to_latin),
    "lat2cyr": ("Lotin → Kirill", latin_to_cyrillic),
}


def convert(mode, text):
    return MODES[mode][1](text)


def detect_mode(text):
    """Matn alifbosiga qarab eng mos rejimni taklif qiladi."""
    cyr = sum(1 for c in text if "а" <= c.lower() <= "я" or c.lower() in "ўқғҳё")
    new = sum(1 for c in text if c in "ÖöĞğŞşÇç")
    if cyr > max(3, new):
        return "cyr2lat"
    if new:
        return "new2lat"
    return "lat2new"


# Eski nom bilan moslik
transliterate_text = latin_to_new

"""Gemini bilan ishlash: matn, JSON (test savollari), rasm (qo'lyozma esse) — qayta urinish va zaxira modellar bilan."""
import json
import re
import threading
import time

from app import config

SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi Fanlar akademiyasi Til va adabiyot instituti yetakchi filologi, "
    "OAK eksperti hamda BMB (DTM) va Milliy sertifikat bo'yicha bosh ilmiy-metodistsiz.\n\n"
    "UMUMIY QOIDALAR:\n"
    "1. Barcha javoblar o'zbek tilida (lotin yozuvi), amaldagi rasmiy imlo va orfoepiyaga mos bo'lsin.\n"
    "2. Aniq bilmagan ma'lumotni to'qimang. Ishonchingiz komil bo'lmasa, buni ochiq ayting.\n"
    "3. Muallif, asar, iqtibos va manbalarni faqat haqiqiy bo'lganda keltiring; sun'iy manba yozmang.\n\n"
    "TEST SAVOLLARI UCHUN:\n"
    "1. Savol, variantlar va izohlar akademik aniqlikda, imloviy-grammatik xatosiz bo'lsin.\n"
    "2. Har bir savolda aynan 4 ta turli variant va bitta mutlaqo to'g'ri javob bo'lsin; "
    "'correct_option_id' to'g'ri variantning 0..3 indeksi bo'lsin.\n"
    "3. Adabiyot savollari amaldagi 5-11-sinf darsliklariga mos bo'lsin.\n\n"
    "TAQIQLAR: diniy aqidaviy bahslar, siyosat va amaldorlar shaxsi, tibbiy va huquqiy maslahat, "
    "ekstremizm va haqoratli mazmun rad etiladi.\n\n"
    "FORMAT: Telegramda o'qishga qulay — qisqa sarlavhalar (##), **qalin** ajratmalar, '-' bilan ro'yxatlar. "
    "Jadval va murakkab Markdown ishlatmang."
)


class AIError(Exception):
    pass


class AIUnavailable(AIError):
    pass


_client = None
_client_lock = threading.Lock()


def _get_client():
    global _client
    with _client_lock:
        if _client is None:
            if not config.GEMINI_API_KEY:
                raise AIUnavailable("GEMINI_API_KEY sozlanmagan.")
            from google import genai
            _client = genai.Client(api_key=config.GEMINI_API_KEY)
        return _client


def _discover_models(client):
    """Sozlangan modellar ishlamasa, hisobda mavjud 'flash' modellarini avtomatik topadi."""
    found = []
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            actions = getattr(m, "supported_actions", None) or []
            if "flash" in name and "generateContent" in actions and not any(x in name for x in ("image", "tts", "live", "audio", "thinking-exp")):
                found.append(name)
    except Exception as e:  # noqa: BLE001
        print(f"[ai] modellar ro'yxatini olib bo'lmadi: {e}")
    return sorted(found, reverse=True)


def _try_models(client, models, contents, cfg):
    from google.genai import types
    last_err = ""
    for model in models:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model, contents=contents, config=types.GenerateContentConfig(**cfg))
                text = (getattr(resp, "text", None) or "").strip()
                if text:
                    return text, ""
                last_err = f"{model}: bo'sh javob"
                break
            except Exception as e:  # noqa: BLE001
                last_err = f"{model}: {e}"
                print(f"[ai] {last_err[:300]}")
                low = str(e).lower()
                if "429" in low or "resource_exhausted" in low:
                    time.sleep(2 + attempt * 2)
                    continue
                if "503" in low or "unavailable" in low or "overloaded" in low or "500" in low:
                    time.sleep(1.5 + attempt)
                    continue
                break
    return None, last_err


def _call(contents, temperature, system, json_mode=False):
    client = _get_client()
    cfg = dict(system_instruction=system, temperature=temperature)
    if json_mode:
        cfg["response_mime_type"] = "application/json"
    text, err = _try_models(client, config.GEMINI_MODELS, contents, cfg)
    if text:
        return text
    if "404" in err or "not found" in err.lower() or "not supported" in err.lower():
        extra = [m for m in _discover_models(client) if m not in config.GEMINI_MODELS]
        if extra:
            print(f"[ai] topilgan modellar: {extra[:4]}")
            text, err2 = _try_models(client, extra[:4], contents, cfg)
            if text:
                config.GEMINI_MODELS[:0] = [m for m in extra[:4]]  # keyingi so'rovlar uchun eslab qolamiz
                return text
            err = err2 or err
    raise AIError(err[:400] or "Noma'lum xatolik")


def generate_text(prompt, temperature=0.3, system=SYSTEM_INSTRUCTION):
    return _call(prompt, temperature, system)


def generate_vision(prompt, image_bytes, mime="image/jpeg", temperature=0.2):
    from google.genai import types

    part = types.Part.from_bytes(data=image_bytes, mime_type=mime)
    return _call([part, prompt], temperature, SYSTEM_INSTRUCTION)


def _extract_json(raw):
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    for open_c, close_c in (("[", "]"), ("{", "}")):
        a, b = raw.find(open_c), raw.rfind(close_c)
        if a != -1 and b > a:
            try:
                return json.loads(raw[a:b + 1])
            except Exception:
                continue
    raise AIError("JSON o'qib bo'lmadi")


def generate_json(prompt, temperature=0.4, system=SYSTEM_INSTRUCTION):
    raw = _call(prompt, temperature, system, json_mode=True)
    return _extract_json(raw)


def validate_question(q):
    """Savol tuzilmasini tekshiradi va tozalaydi; yaroqsiz bo'lsa None."""
    try:
        text = str(q.get("question", "")).strip()
        opts = [str(o).strip() for o in q.get("options", [])]
        idx = int(q.get("correct_option_id", -1))
    except Exception:
        return None
    if not text or len(opts) != 4 or any(not o for o in opts):
        return None
    if len({o.lower() for o in opts}) != 4 or not (0 <= idx < 4):
        return None
    return {
        "question": text,
        "options": opts,
        "correct_option_id": idx,
        "explanation": str(q.get("explanation", "") or "").strip(),
        "bolim": str(q.get("bolim", "") or ""),
    }


_QUIZ_SCHEMA = (
    "Faqat JSON massiv qaytaring, boshqa matn yozmang:\n"
    "[{\"question\": \"Savol matni\", \"options\": [\"A\", \"B\", \"C\", \"D\"], "
    "\"correct_option_id\": 0, \"explanation\": \"Qisqa ilmiy izoh (maks 180 belgi)\"}]"
)


def generate_quiz(topic_prompt, count, seed=None, passage=None):
    """AI orqali `count` ta test savoli. Qisman natija bo'lsa ham mavjudini qaytaradi."""
    seed = seed or int(time.time()) % 100000
    base = (
        f"{topic_prompt}\n\nTO'LIQ {count} TA savol tuzing (seed #{seed}). Har bir savol — 4 variantli, "
        f"bitta to'g'ri javobli, variantlar 90 belgidan oshmasin, savollar bir-birini takrorlamasin.\n"
    )
    if passage:
        base += f"\nSavollar FAQAT quyidagi matn asosida bo'lsin:\n\"\"\"\n{passage[:4000]}\n\"\"\"\n"
    raw = generate_json(base + _QUIZ_SCHEMA, temperature=0.5)
    if isinstance(raw, dict):
        raw = raw.get("questions") or raw.get("tests") or list(raw.values())[0]
    out, seen = [], set()
    for q in raw if isinstance(raw, list) else []:
        v = validate_question(q)
        if v and v["question"].lower() not in seen:
            seen.add(v["question"].lower())
            out.append(v)
    return out

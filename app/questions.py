"""Savollar manbai: tasdiqlangan mahalliy baza (baza.json) + AI generatsiya (parallel, zaxira bilan)."""
import hashlib
import json
import os
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app import ai, config

_bank_lock = threading.Lock()
_bank = None
_raw = None


def _load_raw():
    global _raw
    with _bank_lock:
        if _raw is None:
            try:
                with open(os.path.join(config.DATA_DIR, "baza.json"), "r", encoding="utf-8") as f:
                    _raw = json.load(f)
            except Exception as e:  # noqa: BLE001
                print(f"[bank] baza.json o'qilmadi: {e}")
                _raw = {}
        return _raw


def raw_bank():
    return _load_raw()


def load_bank():
    global _bank
    if _bank is None:
        out = []
        for t in _load_raw().get("tests", []):
            v = ai.validate_question(t)
            if v:
                v["bolim"] = t.get("bolim", "")
                v["id"] = t.get("id", "")
                out.append(v)
        _bank = out
    return _bank


def qkey(q):
    return hashlib.sha1(q["question"].strip().lower().encode("utf-8")).hexdigest()[:12]


_POSITIONAL = re.compile(r"\b[ABCD]\b|hammasi|barcha|yuqoridagi|hech biri|ikkalasi|uchalasi", re.I)


def shuffle_options(q):
    """Variantlarni aralashtiradi (javob 'A' da to'planib qolmasligi uchun). 'A va B' kabi bog'liq variantlar bo'lsa tegmaydi."""
    q = dict(q)
    opts = list(q["options"])
    if any(_POSITIONAL.search(o) for o in opts):
        return q
    correct = opts[q["correct_option_id"]]
    random.shuffle(opts)
    q["options"] = opts
    q["correct_option_id"] = opts.index(correct)
    return q


def bank_pool(sections=None):
    bank = load_bank()
    if not sections:
        return list(bank)
    wanted = {s.lower() for s in sections}
    return [q for q in bank if q.get("bolim", "").lower() in wanted]


def bank_search(topic, limit=30):
    """Erkin mavzu so'zlari bo'yicha bazadan mos savollarni topadi (zaxira sifatida)."""
    words = [w for w in re.findall(r"[\w']{4,}", topic.lower())]
    if not words:
        return []
    scored = []
    for q in load_bank():
        hay = (q["question"] + " " + q.get("bolim", "") + " " + " ".join(q["options"])).lower()
        s = sum(1 for w in words if w[:5] in hay)
        if s:
            scored.append((s, q))
    scored.sort(key=lambda x: -x[0])
    return [q for _, q in scored[:limit]]


def _dedupe(items):
    seen, out = set(), []
    for q in items:
        k = q["question"].strip().lower()
        if k not in seen:
            seen.add(k)
            out.append(q)
    return out


def _split_batches(n, size=10):
    batches = []
    while n > 0:
        b = min(size, n)
        batches.append(b)
        n -= b
    return batches


def _ai_many(prompt, count, passage=None):
    """AI dan `count` ta savolni 10 talik bo'laklarda parallel so'raydi. Xato bo'lgan bo'lak e'tiborsiz."""
    results, errors = [], []

    def work(n):
        try:
            return ai.generate_quiz(prompt, n, seed=random.randint(1000, 99999), passage=passage)
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
            return []

    batches = _split_batches(count)
    with ThreadPoolExecutor(max_workers=min(3, len(batches))) as ex:
        for part in ex.map(work, batches):
            results.extend(part)
    return _dedupe(results), errors


def build_quiz(topic_prompt, count, sections=None, passage=None, free_topic=None):
    """Aralash manba: bazadagi tasdiqlangan savollar + AI. Qaytaradi (savollar, meta)."""
    if sections is not None or free_topic is None:
        pool = bank_pool(sections)
    else:
        pool = bank_search(free_topic)
    random.shuffle(pool)
    if passage:
        pool = []  # matn asosidagi test faqat AI dan
    n_bank = min(len(pool), max(0, count // 3))
    taken = pool[:n_bank]
    leftover = pool[n_bank:]

    ai_qs, errors = [], []
    need = count - len(taken)
    if need > 0:
        ai_qs, errors = _ai_many(topic_prompt, need, passage=passage)

    questions = _dedupe(taken + ai_qs)
    if len(questions) < count and leftover:
        have = {q["question"].lower() for q in questions}
        for q in leftover:
            if len(questions) >= count:
                break
            if q["question"].lower() not in have:
                questions.append(q)
    if not questions:
        raise ai.AIError(errors[0] if errors else "Savol topilmadi")

    random.shuffle(questions)
    questions = [shuffle_options(q) for q in questions[:count]]
    meta = dict(
        requested=count, got=len(questions), ai=len(ai_qs), bank=len(questions) - min(len(ai_qs), len(questions)),
        short=len(questions) < count,
    )
    return questions, meta


def theme_prompt(theme_text):
    return (
        "O'zbekiston Respublikasi BMB (DTM) va Milliy sertifikat standarti bo'yicha, amaldagi 5-11-sinf "
        f"Ona tili va adabiyot darsliklari asosida '{theme_text}' mavzusida Quiz test tuzing. "
        "Darslik faktlariga 100% mos bo'lsin, imlo va grammatik xatolarga yo'l qo'yilmasin."
    )


GENERAL_THEME = "5-11-sinf Ona tili va adabiyot (barcha bo'limlar aralash)"


_LEVEL_TAG = re.compile(r"^\[Y\d\]\s*")


def build_attestation():
    """Attestatsiya: Y1 (15) + Y2 (15) + Y3 (10) — uch parallel so'rov."""
    specs = [
        ("Y1", 15, "Bilish darajasi: qoida, atama va nazariya bo'yicha savollar"),
        ("Y2", 15, "Qo'llash darajasi: matn/gap tahlili, sintaktik va fonetik parchalash, amaliy topshiriqlar"),
        ("Y3", 10, "Mulohaza va metodika: matn teranligi, muammoli metodik vaziyatlar, dars tahlili"),
    ]
    errors = []

    def work(spec):
        tag, n, desc = spec
        try:
            qs = ai.generate_quiz(
                "Maktabgacha va maktab ta'limi vazirligi pedagoglar attestatsiyasi spetsifikatsiyasi asosida "
                f"Ona tili va adabiyot fani o'qituvchilari uchun [{tag}] — {desc}.", n)
            for q in qs:
                clean = _LEVEL_TAG.sub("", q["question"])
                q["question"] = "[" + tag + "] " + clean
            return qs
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
            return []

    with ThreadPoolExecutor(max_workers=3) as ex:
        parts = list(ex.map(work, specs))
    qs = [q for part in parts for q in part]
    if len(qs) < 10:
        raise ai.AIError(errors[0] if errors else "Attestatsiya savollari shakllanmadi")
    return [shuffle_options(q) for q in qs]


def daily_question(date=None):
    """Kun savoli: har kuni hamma uchun bir xil, bazadan deterministik tanlanadi."""
    bank = load_bank()
    if not bank:
        return None
    d = date or datetime.now(config.TZ).date()
    ordered = sorted(bank, key=lambda q: str(q.get("id", "")))
    q = dict(ordered[d.toordinal() % len(ordered)])
    return q


def random_bank_questions(n):
    bank = load_bank()
    return [shuffle_options(q) for q in random.sample(bank, min(n, len(bank)))]

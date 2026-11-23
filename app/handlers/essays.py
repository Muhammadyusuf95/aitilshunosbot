"""Milliy sertifikat esse markazi: tekshiruv (matn/rasm), mavzular, namunalar, sxema."""
import random

from app import config
from app.content import CERT_ESSAY_TOPICS, ESSAY_STRUCTURE, SAMPLE_ESSAYS
from app.db import get_db
from app.handlers.common import bg, on_cb, run_ai_text
from app.handlers.tools import download_photo, photo_state, state_handler
from app.runtime import answer_cb, bot, clear_state, set_state, show
from app.textfmt import card, esc, send_html, send_long
from app.ui import kb, view_samples, view_topics_all

ESSAY_CHECK_PROMPT = (
    "Quyidagi esseni Ona tili va adabiyot fanidan Milliy sertifikat 50 ballik mezoni asosida tekshiring.\n"
    "Taxminiy rubrika (har biri 10 ball): 1) mavzuga mosligi va ikkala qarashni yoritishi; 2) fikrni asoslash "
    "(dalil, misol); 3) kompozitsiya va mantiqiy izchillik; 4) til boyligi va uslub; 5) imlo va punktuatsiya.\n\n"
    "Javob tuzilmasi:\n"
    "## Umumiy ball: X/50\n"
    "## Mezonlar bo'yicha (har biri uchun ball va 1-2 jumla sabab)\n"
    "## Topilgan xatolar (iqtibos → to'g'risi → qisqa qoida)\n"
    "## Kuchli tomonlari\n"
    "## 3 ta aniq tavsiya\n"
    "Ballni halol qo'ying, mubolag'a qilmang. Oxirida: «Eslatma: bu AI baholash — rasmiy ekspert bahosi farq qilishi mumkin.»\n\n"
    "ESSE:\n{input}"
)


@on_cb("essay:check")
def cb_essay_check(call):
    answer_cb(call)
    set_state(call.from_user.id, "essay_check")
    send_html(bot, call.message.chat.id, card(
        "✍️ ESSE TEKSHIRUVI", "50 ballik mezon",
        "Esse <b>mavzusi</b> va <b>matnini</b> to'liq yuboring.\n\n"
        "📷 Qo'lyozma bo'lsa — <b>rasmini</b> yuborishingiz mumkin, bot o'qib, so'ng tekshiradi.\n\n"
        "<i>Bekor qilish: /cancel</i>"))


def run_essay_check(chat_id, user, text=None, photo=None):
    db = get_db()
    if photo:
        prompt = ("Rasmdagi esse matnini avval aynan o'qing (## O'qilgan matn bo'limida), so'ng tekshiring.\n"
                  + ESSAY_CHECK_PROMPT.replace("{input}", "(rasmdagi esse)"))
        bg(_checked, chat_id, user, prompt, None, photo)
    else:
        prompt = ESSAY_CHECK_PROMPT.replace("{input}", (text or "")[:6000])
        bg(_checked, chat_id, user, prompt, text, None)


def _checked(chat_id, user, prompt, check_text, photo):
    ok = run_ai_text(chat_id, user, prompt, "Esse tekshiruvi", "", check_text, vision=photo)
    if ok:
        db = get_db()
        n = db.kv_incr(f"essays:{user.id}")
        if n >= 3:
            db.award_badge(user.id, "essay_pro")


@state_handler("essay_check")
def st_essay_check(message, st):
    text = (message.text or "").strip()
    if len(text) < 80:
        send_html(bot, message.chat.id, "✍️ Esse juda qisqa ko'rinadi. Iltimos, mavzu va to'liq matnni yuboring.")
        return
    clear_state(message.from_user.id)
    run_essay_check(message.chat.id, message.from_user, text)


@photo_state("essay_check")
def st_essay_photo(message, st):
    clear_state(message.from_user.id)
    run_essay_check(message.chat.id, message.from_user, photo=download_photo(message))


# ---------------- Mavzular ----------------
@on_cb("topics:all")
def cb_topics_all(call):
    answer_cb(call)
    show(call, *view_topics_all())


@on_cb("topics:new")
def cb_topics_new(call):
    answer_cb(call, "AI mavzular tayyorlamoqda…")
    prompt = ("O'zbekiston Respublikasi Ona tili va adabiyot fanidan Milliy sertifikat standarti asosida dolzarb "
              "5 ta ORIGINAL ESSE MAVZUSINI tuzing. Har bir mavzuda ikkala qarama-qarshi nuqtayi nazar aniq ifodalansin "
              "(\"Ba'zilar ... deb hisoblasa, ayrimlar ... deb biladi\" shaklida). Diniy va siyosiy mavzular bo'lmasin.")
    bg(run_ai_text, call.message.chat.id, call.from_user, prompt, "Yangi esse mavzulari", "", None)


@on_cb("essay:rand")
def cb_essay_rand(call):
    answer_cb(call)
    topic = random.choice(CERT_ESSAY_TOPICS)
    markup = kb([[("🎲 Boshqa mavzu", "essay:rand"), ("✍️ Yozib tekshirtiraman", "essay:check")],
                 [("🔙 Esse markaziga", "hub:cert")]])
    show(call, card("🎲 TASODIFIY MAVZU", "25-30 daqiqada yozib ko'ring", esc(topic)), markup)


@on_cb("essay:struct")
def cb_essay_struct(call):
    answer_cb(call)
    show(call, ESSAY_STRUCTURE, kb([[("✍️ Esse tekshiruvi", "essay:check")], [("🔙 Esse markaziga", "hub:cert")]]))


# ---------------- Namunalar ----------------
@on_cb("samples:")
def cb_samples(call):
    answer_cb(call)
    show(call, *view_samples(int(call.data.split(":")[1])))


@on_cb("essay:read:")
def cb_essay_read(call):
    answer_cb(call)
    eid = int(call.data.split(":")[2])
    found = next((e for e in SAMPLE_ESSAYS if e["id"] == eid), None)
    if not found:
        answer_cb(call, "Esse topilmadi", True)
        return
    head = (f"<b>📝 NAMUNAVIY ESSE #{found['id']}</b>\n━━━━━━━━━━━━━━━\n"
            f"📌 <b>Mavzu:</b> <i>{esc(found['topic'])}</i>\n\n")
    foot = "\n\n━━━━━━━━━━━━━━━\n🏆 <i>Milliy sertifikat 50 ballik standartiga mos namuna</i>"
    markup = kb([[("📚 Ro'yxatga qaytish", "samples:0"), ("🎯 Esse markazi", "hub:cert")]])
    from app.textfmt import split_source
    parts = split_source(found["text"], 3000)
    for i, part in enumerate(parts):
        txt = (head if i == 0 else "") + esc(part) + (foot if i == len(parts) - 1 else "")
        send_html(bot, call.message.chat.id, txt, reply_markup=markup if i == len(parts) - 1 else None)


@on_cb("essay:aiwrite")
def cb_essay_aiwrite(call):
    answer_cb(call)
    set_state(call.from_user.id, "essay_write")
    send_html(bot, call.message.chat.id, "✍️ <b>Qaysi mavzuda namunaviy esse yozib beray?</b>\nMavzuni to'liq yuboring:")


@state_handler("essay_write")
def st_essay_write(message, st):
    topic = (message.text or "").strip()
    if len(topic) < 10:
        send_html(bot, message.chat.id, "Mavzuni to'liqroq yozing, iltimos.")
        return
    clear_state(message.from_user.id)
    prompt = ("Ona tili va adabiyoti fanidan Milliy sertifikat 50 ballik mezonlari asosida quyidagi mavzuda namunaviy "
              "esse yozing (250-350 so'z): qisqa kirish, ikkala qarashni dalil bilan yoritish, shaxsiy pozitsiya, xulosa. "
              "Til boy, imlo va punktuatsiya aniq bo'lsin.\n\nMavzu: " + topic[:600])
    bg(run_ai_text, message.chat.id, message.from_user, prompt, "Namunaviy esse", "", topic)

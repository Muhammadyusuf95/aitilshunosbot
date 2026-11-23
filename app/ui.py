"""Interfeys: klaviaturalar va "kartochka" ko'rinishidagi ekranlar. Har bir view_* funksiya (html, markup) qaytaradi."""
from telebot import types as tt

from app import config
from app.content import CERT_ESSAY_TOPICS, SAMPLE_ESSAYS, SECTIONS, THEME_CATALOG, TOOLS
from app.runtime import webapp_url
from app.textfmt import card, esc

# ---------------- Asosiy menyu tugmalari ----------------
BTN_ABIT = "🎒 Abituriyent"
BTN_TEACH = "👨‍🏫 O'qituvchi"
BTN_STUDENT = "🎓 Talaba"
BTN_RESEARCH = "🔬 Tadqiqotchi"
BTN_DAILY = "⚡ Kun savoli"
BTN_TOOLS = "🧰 Til asboblari"
BTN_QUIZ = "🛠 Quiz yaratish"
BTN_RANK = "🏆 Reyting"
BTN_PROFILE = "👤 Shaxsiy kabinet"
BTN_ADMIN = "👑 Admin paneli"

MENU_ACTIONS = {
    BTN_ABIT: "abit", BTN_TEACH: "oqituvchi", BTN_STUDENT: "talaba", BTN_RESEARCH: "izlanuvchi",
    BTN_DAILY: "daily", BTN_TOOLS: "asboblar", BTN_QUIZ: "quiz", BTN_RANK: "rank",
    BTN_PROFILE: "profile", BTN_ADMIN: "admin",
    # Eski klaviatura yozuvlari ham ishlayversin
    "🎓 Talabalar uchun": "talaba", "👨‍🏫 O'qituvchilar uchun": "oqituvchi", "🎒 Abituriyentlar uchun": "abit",
    "🔬 Ilmiy izlanuvchilar uchun": "izlanuvchi", "🛠 Quiz Test Tuzuvchi": "quiz", "🏆 Jonli Reyting Doskasi": "rank",
    "🔠 Yangi Alifbo": "conv", "📖 Kun hikmati & Motivatsiya (Admin)": "admin", "📊 Boshqaruv & Statistika": "admin",
    "🔙 Asosiy menyu": "menu",
}


def main_menu(uid=None):
    m = tt.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, input_field_placeholder="So'z, matn yoki bayt yuboring…")
    m.row(tt.KeyboardButton(BTN_ABIT), tt.KeyboardButton(BTN_TEACH))
    m.row(tt.KeyboardButton(BTN_STUDENT), tt.KeyboardButton(BTN_RESEARCH))
    m.row(tt.KeyboardButton(BTN_DAILY), tt.KeyboardButton(BTN_TOOLS))
    m.row(tt.KeyboardButton(BTN_QUIZ), tt.KeyboardButton(BTN_RANK))
    m.row(tt.KeyboardButton(BTN_PROFILE))
    if uid is not None and int(uid) == int(config.ADMIN_ID):
        m.row(tt.KeyboardButton(BTN_ADMIN))
    return m


# ---------------- Inline klaviatura yasovchi ----------------
def kb(rows):
    """rows: [[(matn, qiymat[, tur]), ...], ...]; tur: cb (standart) | url | web | switch."""
    m = tt.InlineKeyboardMarkup()
    for row in rows:
        btns = []
        for item in row:
            if not item:
                continue
            text, val = item[0], item[1]
            kind = item[2] if len(item) > 2 else "cb"
            if kind == "url":
                btns.append(tt.InlineKeyboardButton(text=text, url=val))
            elif kind == "web":
                btns.append(tt.InlineKeyboardButton(text=text, web_app=tt.WebAppInfo(url=val)))
            elif kind == "switch":
                btns.append(tt.InlineKeyboardButton(text=text, switch_inline_query=val))
            else:
                btns.append(tt.InlineKeyboardButton(text=text, callback_data=val))
        if btns:
            m.row(*btns)
    return m


def rank_btn(label="🏆 Reyting doskasi"):
    url = webapp_url()
    return (label, url, "web") if url else (label, "rank:top")


# ---------------- Ekranlar ----------------
def view_section(key):
    sec = SECTIONS[key]
    rows = [[(TOOLS[t]["title"], f"tool:{t}")] for t in sec["tools"]]
    for label, cb in sec.get("extra", []):
        rows.append([(label, cb)])
    rows.append([rank_btn()])
    body = "\n".join(f"▫️ {TOOLS[t]['title']}" for t in sec["tools"])
    return card(sec["title"], sec["sub"], body + "\n\n👇 <i>Kerakli bo'limni tanlang:</i>"), kb(rows)


def view_abit():
    rows = [
        [("🎯 Milliy sertifikat esselari", "hub:cert")],
        [("⚡ Tezkor test (10 ta)", "quick:10"), ("🧠 BMB 30 talik", "bmb30")],
        [("📚 Mavzulashtirilgan test", "hub:themes")],
        [("🔁 Xatolar ustida ishlash", "review:start")],
        [(TOOLS["izoh"]["title"], "tool:izoh")],
        [rank_btn()],
    ]
    body = (
        "▫️ <b>Esse:</b> tekshiruv, mavzular banki, namunalar va sxema\n"
        "▫️ <b>Tezkor test:</b> 10 ta savol, har biridan so'ng izoh\n"
        "▫️ <b>BMB 30 talik:</b> davlat imtihoni standarti\n"
        "▫️ <b>Xatolar ustida ishlash:</b> adashgan savollaringiz qayta beriladi\n"
        "▫️ <b>O'TIL izohi</b> va imlo"
    )
    return card("🎒 ABITURIYENT MARKAZI", "Milliy sertifikat · BMB · esse", body + "\n\n👇 <i>Tanlang:</i>"), kb(rows)


def view_cert():
    rows = [
        [("✍️ Esse tekshiruvi (50 ballik)", "essay:check")],
        [("💡 Esse mavzulari", "hub:topics"), ("🎲 Tasodifiy mavzu", "essay:rand")],
        [("📚 Namunaviy esselar", "samples:0"), ("📐 Esse sxemasi", "essay:struct")],
        [("🔙 Abituriyent markaziga", "hub:abit")],
    ]
    body = (
        "▫️ <b>Tekshiruv:</b> matn yoki qo'lyozma <u>rasmini</u> yuboring — 5 mezon bo'yicha ball va xatolar tahlili\n"
        f"▫️ <b>Mavzular:</b> {len(CERT_ESSAY_TOPICS)} ta rasmiy mavzu + AI taklifi\n"
        f"▫️ <b>Namunalar:</b> {len(SAMPLE_ESSAYS)} ta tayyor esse\n"
        "▫️ <b>Sxema:</b> kirish → qarashlar → pozitsiya → xulosa"
    )
    return card("🎯 MILLIY SERTIFIKAT ESSELARI", "50 ballik baholash mezoni asosida", body), kb(rows)


def view_topics_hub():
    rows = [
        [(f"📋 {len(CERT_ESSAY_TOPICS)} ta tayyor mavzu", "topics:all")],
        [("✨ AI orqali yangi mavzular", "topics:new")],
        [("🔙 Esse markaziga", "hub:cert")],
    ]
    return card("💡 ESSE MAVZULARI", "Milliy sertifikat yo'nalishlari", "Tayyor bankdan tanlang yoki AI dan yangi mavzu so'rang."), kb(rows)


def view_topics_all():
    body = "\n\n".join(f"<b>{i}.</b> {esc(t)}" for i, t in enumerate(CERT_ESSAY_TOPICS, 1))
    rows = [[("✨ AI orqali yangi mavzu", "topics:new")], [("🔙 Mavzular bo'limiga", "hub:topics")]]
    return card(f"📋 {len(CERT_ESSAY_TOPICS)} TA RASMIY MAVZU", "", body), kb(rows)


def view_samples(page=0, per_page=5):
    total = len(SAMPLE_ESSAYS)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    chunk = SAMPLE_ESSAYS[page * per_page:(page + 1) * per_page]
    rows = [[(f"📖 {e['id']}. {e['title']}"[:60], f"essay:read:{e['id']}")] for e in chunk]
    nav = []
    if page > 0:
        nav.append(("⬅️ Oldingi", f"samples:{page - 1}"))
    if page + 1 < pages:
        nav.append(("Keyingi ➡️", f"samples:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([("✍️ Yangi mavzuda AI namunaviy esse", "essay:aiwrite")])
    rows.append([("🔙 Esse markaziga", "hub:cert")])
    body = f"📄 Sahifa <b>{page + 1}/{pages}</b> · jami {total} ta namuna\n\nO'qimoqchi bo'lgan essengizni tanlang:"
    return card("📚 NAMUNAVIY ESSELAR", "Milliy sertifikat mezonlariga mos", body), kb(rows)


def view_themes_hub():
    rows = [
        [("📂 Katalogdan tanlash", "themes:catalog")],
        [("✍️ O'z mavzuimni kiritaman", "themes:custom")],
        [("🔙 Abituriyent markaziga", "hub:abit")],
    ]
    body = ("1️⃣ <b>Katalog</b> — 5-11-sinf darsliklarining asosiy bo'limlari\n"
            "2️⃣ <b>Erkin mavzu</b> — aniq dars yoki tor yo'nalish nomini yozasiz")
    return card("📚 MAVZULASHTIRILGAN TEST", "30 talik BMB formati", body), kb(rows)


def view_theme_catalog():
    rows = [[(v[0], f"theme:{k}")] for k, v in THEME_CATALOG.items()]
    rows.append([("🔙 Orqaga", "hub:themes")])
    return card("📂 MAVZULAR KATALOGI", "Qaysi bo'limdan 30 talik test?", "Bo'limni tanlang:"), kb(rows)


def view_quiz_hub():
    rows = [[("🚀 Yangi quiz yaratish", "qb:start")], [rank_btn()]]
    body = (
        "O'zingiz xohlagan <b>mavzu</b> yoki <b>darslik parchasi</b> asosida 4 variantli test tuzing.\n\n"
        "✨ <b>Imkoniyatlar</b>\n"
        "▫️ 5 dan 30 tagacha savol\n"
        "▫️ Yakka mashq (izoh bilan) yoki vaqtli quiz (15/30/45 soniya)\n"
        "▫️ Guruhga yuborib, <b>jonli bellashuv</b> o'tkazish\n"
        "▫️ Matn yuborsangiz — savollar aynan shu matndan tuziladi"
    )
    return card("🛠 QUIZ KONSTRUKTORI", "AI + tasdiqlangan baza", body), kb(rows)


def view_conv_hub():
    rows = [
        [("🔤 Lotin → Yangi (Ö Ğ Ş Ç)", "conv:lat2new")],
        [("🔡 Yangi → Lotin", "conv:new2lat")],
        [("Кирилл → Lotin", "conv:cyr2lat"), ("Lotin → Кирилл", "conv:lat2cyr")],
        [("🔙 Til asboblari", "hub:asboblar")],
    ]
    body = ("Rejimni tanlang va matnni yuboring. Matn hajmi cheklanmagan.\n\n"
            "<i>Maslahat: matnni to'g'ridan-to'g'ri yuborsangiz, bot alifboni o'zi aniqlab taklif qiladi.</i>")
    return card("🔠 ALIFBO KONVERTORI", "Lotin · Kirill · Yangi alifbo", body), kb(rows)


def view_sfx_hub():
    rows = [
        [("Ot yasalishi", "sfx:ot"), ("Sifat yasalishi", "sfx:sifat")],
        [("Fe'l yasalishi", "sfx:fel"), ("Ravish yasalishi", "sfx:ravish")],
        [("🔙 Til asboblari", "hub:asboblar")],
    ]
    body = ("Tasdiqlangan jadval asosida (AI'siz, bir zumda).\n\n"
            "🔎 <b>Qidirish:</b> qo'shimchani (masalan <code>-chi</code>) yoki so'zni (masalan <code>o'quvchi</code>) "
            "yozib yuboring — o'zi topadi.")
    return card("🧩 SO'Z YASOVCHI QO'SHIMCHALAR", "Ot · sifat · fe'l · ravish", body), kb(rows)

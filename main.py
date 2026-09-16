import os
import threading
import json
import random
import time
from datetime import datetime
import pytz
import requests
from flask import Flask, render_template_string
import telebot
from telebot import types as tele_types
from google import genai
from google.genai import types

# --- RENDER WEB SERVICE VA TELEGRAM WEBAPP SERVERI ---
app = Flask(__name__)
RESULTS_FILE = "test_results.json"
USERS_FILE = "users.json"
COUNTERS_FILE = "quiz_counters.json"

def load_data(filepath):
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

WEBAPP_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>BMB Test Reytingi & Statistika</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --primary: #38bdf8;
      --accent: #f59e0b;
      --text: #f8fafc;
      --text-dim: #94a3b8;
    }
    body {
      margin: 0;
      padding: 16px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background-color: var(--bg);
      color: var(--text);
    }
    .header {
      text-align: center;
      margin-bottom: 20px;
    }
    .badge {
      display: inline-block;
      padding: 4px 12px;
      background: rgba(56, 189, 248, 0.15);
      color: var(--primary);
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 8px;
    }
    h1 {
      font-size: 20px;
      margin: 0 0 6px 0;
    }
    .sub {
      color: var(--text-dim);
      font-size: 13px;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 18px;
    }
    .stat-card {
      background: var(--card);
      padding: 12px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.05);
      text-align: center;
    }
    .stat-val {
      font-size: 18px;
      font-weight: bold;
      color: var(--primary);
    }
    .stat-lbl {
      font-size: 11px;
      color: var(--text-dim);
      margin-top: 2px;
    }
    .leaderboard {
      background: var(--card);
      border-radius: 16px;
      padding: 12px;
      border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .row {
      display: flex;
      align-items: center;
      padding: 10px 8px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    .row:last-child {
      border-bottom: none;
    }
    .rank {
      width: 28px;
      font-weight: 700;
      font-size: 14px;
    }
    .rank-1 { color: #fbbf24; }
    .rank-2 { color: #94a3b8; }
    .rank-3 { color: #d97706; }
    .info {
      flex: 1;
      padding: 0 8px;
    }
    .name {
      font-size: 14px;
      font-weight: 600;
    }
    .details {
      font-size: 11px;
      color: var(--text-dim);
    }
    .score {
      font-weight: 700;
      color: var(--primary);
      font-size: 14px;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="badge">MILLIY SERTIFIKAT & BMB</div>
    <h1>🏆 Jonli Reyting Doskasi</h1>
    <div class="sub">@onatilidanyordam hamjamiyati</div>
  </div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-val">{{ total_users }}</div>
      <div class="stat-lbl">Faol Bot A'zolari</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">{{ total_tested }}</div>
      <div class="stat-lbl">Sinovdan O'tganlar</div>
    </div>
  </div>

  <div class="leaderboard">
    {% for user in top_users %}
    <div class="row">
      <div class="rank rank-{{ user.rank }}">{{ user.rank_icon }}</div>
      <div class="info">
        <div class="name">{{ user.name }}</div>
        <div class="details">{{ user.date }} • ⏳ {{ user.duration_str }}</div>
      </div>
      <div class="score">{{ user.correct }}/30</div>
    </div>
    {% else %}
    <div style="text-align: center; padding: 20px; color: var(--text-dim); font-size: 13px;">
      Hozircha natijalar mavjud emas. Birinchi bo'lib test topshiring!
    </div>
    {% endfor %}
  </div>

  <script>
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
    }
  </script>
</body>
</html>
"""

@app.route('/')
def home():
    return "AI Tilshunos & Metodist v10.5 (Theme Catalog Edition) Faol!"

@app.route('/leaderboard')
def webapp_leaderboard():
    results = load_data(RESULTS_FILE)
    users = load_data(USERS_FILE)
    sorted_res = sorted(results.items(), key=lambda x: (-x[1].get("correct", 0), x[1].get("duration", 999999)))[:20]
    
    top_list = []
    for idx, (uid, info) in enumerate(sorted_res, 1):
        icon = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"#{idx}"
        dur = info.get("duration", 0)
        dur_str = f"{dur//60}m {dur%60}s"
        top_list.append({
            "rank": idx,
            "rank_icon": icon,
            "name": info.get("name", "Ishtirokchi"),
            "correct": info.get("correct", 0),
            "duration_str": dur_str,
            "date": info.get("date", "")
        })

    return render_template_string(
        WEBAPP_HTML,
        total_users=len(users),
        total_tested=len(results),
        top_users=top_list
    )

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- SERVERNI UYG'OQ SAQLASH ---
RENDER_APP_URL = "https://aitilshunosbot.onrender.com"

def keep_alive():
    while True:
        try:
            time.sleep(600)
            requests.get(RENDER_APP_URL)
        except Exception:
            pass

threading.Thread(target=keep_alive, daemon=True).start()

# --- ASOSIY SOZLAMALAR ---
TELEGRAM_TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@onatilidanyordam"
ADMIN_ID = 5423849679

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

ACTIVE_QUIZ_TRACKER = {}
POLL_CORRECT_MAP = {}
READY_MATCHES = {}
ADMIN_POST_STORAGE = {}
PENDING_QUIZZES = {}

BANNER_IMAGES = {
    "talaba": "https://images.unsplash.com/photo-1457369804613-52c61a468e7d?w=900&auto=format&fit=crop&q=80",
    "oqituvchi": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=900&auto=format&fit=crop&q=80",
    "abituriyent": "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=900&auto=format&fit=crop&q=80",
    "izlanuvchi": "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=900&auto=format&fit=crop&q=80"
}

IMZO = (
    "\n\n╭───────────────────────╮\n"
    f"  🏛 **Rasmiy kanal:** {CHANNEL_USERNAME}\n"
    "  ✨ **AI Asistent:** @aitilshunosbot\n"
    "╰───────────────────────╯"
)

def get_next_quiz_number(quiz_type):
    counters = load_data(COUNTERS_FILE)
    current = counters.get(quiz_type, 0) + 1
    counters[quiz_type] = current
    save_data(COUNTERS_FILE, counters)
    return current

# --- MUKAMMAL MAVZULAR KATALOGI (BMB / DARSLIKLAR STANDARTI) ---
THEME_CATALOG = {
    "cat_fonetika": {
        "title": "🗣 Fonetika, orfoepiya va imlo qoidalari",
        "prompt": "Fonetika: unli va undoshlar tasnifi, tovush o'zgarishlari (tushish, ortish, almashish), bo'g'in, urg'u hamda rasmiy imlo mezonlari"
    },
    "cat_leksika": {
        "title": "📖 Leksikologiya, frazeologiya va paronimlar",
        "prompt": "Leksikologiya: o'z va o'zlashgan qatlam, ma'nodosh, shakldosh, zid ma'noli so'zlar, paronimlar lug'ati va frazeologik iboralar tahlili"
    },
    "cat_morf_mustaqil": {
        "title": "🧩 Morfologiya: Mustaqil so'z turkumlari",
        "prompt": "Mustaqil so'z turkumlari: ot, sifat, son, olmosh, ravish hamda fe'l nisbatlari, vazifa shakllari (sifatdosh, ravishdosh, harakat nomi)"
    },
    "cat_morf_yordamchi": {
        "title": "🔗 Morfologiya: Yordamchi so'zlar va alohida guruh",
        "prompt": "Yordamchi so'zlar (ko'makchi, bog'lovchi, yuklama), modal so'zlar, taqlidlar va undov so'zlar uslubiyati hamda imlosi"
    },
    "cat_sintaksis": {
        "title": "📐 Sintaksis: Gap bo'laklari va qo'shma gaplar",
        "prompt": "Sintaksis: so'z birikmasi, bosh va ikkinchi darajali bo'laklar, uyushiq/ajratilgan bo'laklar, ergashgan qo'shma gaplar va punktuatsiya"
    },
    "cat_mumtoz": {
        "title": "📜 Mumtoz adabiyot va badiiy san'atlar",
        "prompt": "Mumtoz adabiyot: Alisher Navoiy va Bobur ijodi, aruz vazni bahr va ruknlari, mumtoz she'riy janrlar hamda badiiy san'atlar (tazod, tanosub, istiora, iyhom)"
    },
    "cat_jadid": {
        "title": "💡 Jadid va XX asr o'zbek adabiyoti",
        "prompt": "Jadid va XX asr adabiyoti: Behbudiy, Avloniy, Fitrat, Cho'lpon, Qodiriy, Oybek, G'afur G'ulom asarlari va qahramonlari tahlili"
    }
}

# --- TARIXIY DAVRLAR ROTATSIYASI ---
HISTORICAL_EPOCHS = [
    {
        "epoch": "Qadimgi va ilk o'rta asrlar turkiy yozma obidalari (XI-XII asrlar)",
        "sources": "Yusuf Xos Hojibning 'Qutadg'u bilig', Mahmud Koshg'ariyning 'Devonu lug'atit turk', Ahmad Yugnakiyning 'Hibat ul-haqoyiq' yoki Kul tegin / To'nyuquq bitiklari"
    },
    {
        "epoch": "Temuriylar davri va Oltin asr mumtoz adabiyoti (XV-XVI asrlar)",
        "sources": "Alisher Navoiy ('Mahbub ul-qulub', 'Nazm ul-javohir', 'Xamsa'), Zahiriddin Muhammad Bobur ('Boburnoma', 'Mubayyin'), Lutfiy yoki Husayn Boyqaro asarlari"
    },
    {
        "epoch": "XVII-XIX asrlar o'zbek mumtoz adabiyoti va ma'rifati",
        "sources": "Boborahim Mashrab, Turdi Forog'iy, Muhammadrizo Ogahiy ('Riyoz ud-davla', 'Gulshani davlat'), Munis Xorazmiy yoki Nodirabegim asarlari"
    },
    {
        "epoch": "XX asr boshi Jadid ma'rifatparvarlik harakati davri",
        "sources": "Mahmudxo'ja Behbudiy maqolalari, Abdulla Avloniy ('Turkiy Guliston yoxud axloq'), Munavvarqori Abdurashidxonov, Abdurauf Fitrat ('Rahbari najot') yoki Abdulhamid Cho'lpon publitsistikasi"
    },
    {
        "epoch": "XX asr o'zbek adabiyoti durdonalari va ma'rifiy merosi",
        "sources": "Abdulla Qodiriy ('O'tkan kunlar', 'Mehrobdan chayon'), Muso Toshmuhammad o'g'li Oybek, G'afur G'ulom, Erkin Vohidov ('Donishqishloq latifalari', 'Daftari ruhiyat'), Abdulla Oripov yoki O'tkir Hoshimov ('Daftar hoshiyasidagi bitiklar')"
    }
]

# --- QAT'IY XAVFSIZLIK FILTRI ---
FORBIDDEN_KEYWORDS = [
    "prezident", "mirziyoyev", "hokim", "vazir", "hukumat", "davlat boshqaruvi", 
    "siyosat", "saylov", "muxolifat", "deputat", "amaldor", "partiya", "vazirlik",
    "din", "islom", "namoz", "hadis", "oyat", "qur'on", "shariat", "masjid",
    "xristian", "cherkov", "yahudiy", "fatvo", "ro'za", "mulla", "imom", "taqvo",
    "sud", "prokuror", "advokat", "jinoyat kodeksi", "modda", "qamoq", "tibbiyot",
    "davolash", "dori", "kasallik", "tashxis", "shifokor", "retsept",
    "ekstremizm", "terrorizm", "jihod", "vahobiy", "hizb", "inqilob", "qurol", "portlash",
    "ahmoq", "tentak", "haromi", "iflos", "padar", "fosiq", "kofir", "fahisha", "jalab"
]

def check_security_violation(text):
    if not text:
        return False
    lower = text.lower()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in lower:
            return True
    return False

SECURITY_WARNING = (
    "╭─ ⚠️ **QAT'IY ETIKA VA ME'YOR BILDIRISHNOMASI** ─╮\n\n"
    "Bot faqat **Ona tili, adabiyot va dars metodikasi** yo'nalishida "
    "ilmiy-amaliy xizmat ko'rsatadi.\n\n"
    "> *Diniy, siyosiy, huquqiy, tibbiy, davlat boshqaruvi va amaldorlari, "
    "shuningdek, buzg'unchilik va haqoratli mazmundagi so'rovlar 100% taqiqlanadi!*\n\n"
    "╰─────────────────────────────────────────────╯"
)

def save_user(user):
    users = load_data(USERS_FILE)
    u_id = str(user.id)
    if u_id not in users:
        users[u_id] = {
            "first_name": user.first_name or "",
            "username": user.username or "",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_data(USERS_FILE, users)

def get_main_menu(user_id=None):
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(
        tele_types.KeyboardButton("🎓 Talabalar uchun"),
        tele_types.KeyboardButton("👨‍🏫 O'qituvchilar uchun")
    )
    markup.row(
        tele_types.KeyboardButton("🎒 Abituriyentlar uchun"),
        tele_types.KeyboardButton("🔬 Ilmiy izlanuvchilar uchun")
    )
    if user_id and int(user_id) == int(ADMIN_ID):
        markup.row(
            tele_types.KeyboardButton("☀️ Kun hikmati (Admin)"),
            tele_types.KeyboardButton("⚡️ Motivatsiya (Admin)")
        )
        markup.row(tele_types.KeyboardButton("📊 Boshqaruv & Statistika"))
    return markup

# --- BANNER-CARD BILAN BO'LIMLARNI YUBORISH ---
def send_section_card(chat_id, group_name):
    if group_name == "talaba":
        img = BANNER_IMAGES["talaba"]
        caption = (
            "╭──── 🎓 **TALABALAR VA FILOLOGLAR KABINETI** ────╮\n\n"
            "▫️ Mumtoz g'azaliyot badiiyati va poetik san'atlar\n"
            "▫️ Aruz tizimi: hijolar vazni, bahrlar va taf'ilalar\n"
            "▫️ Eski turkiy til manbalari hamda nodir leksik qatlam\n"
            "▫️ Rahmatullayev etimologik lug'ati asosidagi tahlillar\n\n"
            "👇 *Kerakli tahlil turini quyidagi tugmalardan tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=2)
        markup.row(
            tele_types.InlineKeyboardButton(text="📜 G'azal tahlili", callback_data="btn_gazal"),
            tele_types.InlineKeyboardButton(text="📐 Aruz hisoblagich", callback_data="btn_aruz")
        )
        markup.row(
            tele_types.InlineKeyboardButton(text="🏛 Qadimgi turkiy", callback_data="btn_qadim"),
            tele_types.InlineKeyboardButton(text="🔍 So'z etimologiyasi", callback_data="btn_etim")
        )
        bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown", reply_markup=markup)

    elif group_name == "oqituvchi":
        img = BANNER_IMAGES["oqituvchi"]
        caption = (
            "╭──── 👨‍🏫 **METODIST VA O'QITUVCHILAR KABINETI** ────╮\n\n"
            "▫️ Yangi DTS bo'yicha 45 daqiqalik dars konspektlari\n"
            "▫️ Zamonaviy interfaol metodlar (Blum, FSMU, Ven diagrammasi)\n"
            "▫️ **Attestatsiya 40 talik Testi:** Y1 (Bilish), Y2 (Qo'llash), Y3 (Mulohaza)\n\n"
            "👇 *Kerakli amaliyotni tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="📋 45 daqiqalik Dars Ishlanmasi", callback_data="btn_konspekt"),
            tele_types.InlineKeyboardButton(text="🎯 Interfaol Pedagogik Metod", callback_data="btn_metod"),
            tele_types.InlineKeyboardButton(text="📝 Attestatsiya Testi (40 ta Y1, Y2, Y3)", callback_data="btn_attest")
        )
        bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown", reply_markup=markup)

    elif group_name == "abituriyent":
        img = BANNER_IMAGES["abituriyent"]
        caption = (
            "╭──── 🎒 **ABITURIYENT VA SERTIFIKAT MARKAZI** ────╮\n\n"
            "▫️ Milliy sertifikat 50 ballik esse tahlili va mezonlari\n"
            "▫️ O'TIL izohli lug'ati, rasmiy imlo va orfoepiya qoidalari\n"
            "▫️ **BMB 30 talik Test:** Davlat imtihoni standarti (30 soniya)\n"
            "▫️ **Mavzuli BMB Test:** Mukammal katalog yoki erkin mavzu tanlovi\n\n"
            "👇 *Kerakli tayyorgarlik bo'limini tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="📝 Esse tekshiruvi (50 ballik)", callback_data="btn_esse"),
            tele_types.InlineKeyboardButton(text="📖 So'z izohi (O'TIL) & Imlo", callback_data="btn_izoh"),
            tele_types.InlineKeyboardButton(text="🧠 BMB Umumiy 30 talik Test (№)", callback_data="btn_bmb_gen"),
            tele_types.InlineKeyboardButton(text="📚 Mavzulashtirilgan BMB Test (30 ta)", callback_data="btn_bmb_themed_hub"),
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi (Mini-App)", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            )
        )
        bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown", reply_markup=markup)

    elif group_name == "izlanuvchi":
        img = BANNER_IMAGES["izlanuvchi"]
        caption = (
            "╭──── 🔬 **ILMIY TADQIQOT VA DOKTORANTURA** ────╮\n\n"
            "▫️ OAK talabidagi ilmiy maqola (IMRAD standarti rejasi)\n"
            "▫️ Xalqaro va Respublika ilmiy konferensiya tezislari\n"
            "▫️ Dissertatsiya ilmiy apparati va metodologiya yo'riqnomasi\n\n"
            "👇 *Loyihalashtirmoqchi bo'lgan ilmiy yo'nalishni tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="📑 Ilmiy Maqola Konstruktori (OAK)", callback_data="btn_maqola"),
            tele_types.InlineKeyboardButton(text="📄 Konferensiya Tezisi Loyihasi", callback_data="btn_tezis")
        )
        bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown", reply_markup=markup)

# --- MAVZULASHTIRILGAN TEST BOSHQARUV MARKAZI (KATALOG YOKI ERKIN KIRITISH) ---
def send_themed_test_hub(chat_id):
    caption = (
        "╭── 📚 **MAVZULASHTIRILGAN BMB TEST MARKAZI** ──╮\n\n"
        "Ona tili va adabiyoti fanidan 30 talik test topshirish uchun "
        "o'zingizga qulay usulni tanlang:\n\n"
        "1️⃣ **Mavzular katalogidan tanlash** — 5-11-sinf darsliklarining asosiy bo'limlari bo'yicha tayyor ro'yxat;\n"
        "2️⃣ **Mavzuni o'zingiz kiritish** — aniq dars yoki tor yo'nalish nomini yozasiz, bot test tuzib beradi.\n\n"
        "👇 *Tanlang:* \n"
        "╰─────────────────────────────────────────────╯"
    )
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(text="📂 Mavzular Katalogidan tanlash", callback_data="theme_open_catalog"),
        tele_types.InlineKeyboardButton(text="✍️ O'zim yangi mavzu kiritaman", callback_data="theme_custom_input")
    )
    bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)

def send_theme_catalog(chat_id):
    caption = (
        "╭── 📂 **5-11-SINF DARSLIKLARI MAVZULAR KATALOGI** ──╮\n\n"
        "BMB standarti bo'yicha qaysi bo'limdan 30 talik test topshirmoqchisiz?\n"
        "Quyidagi ro'yxatdan kerakli bo'limni tanlang:\n\n"
        "╰──────────────────────────────────────────────╯"
    )
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    for cat_key, cat_data in THEME_CATALOG.items():
        markup.add(tele_types.InlineKeyboardButton(text=cat_data["title"], callback_data=f"seltheme_{cat_key}"))
    markup.add(tele_types.InlineKeyboardButton(text="🔙 Orqaga", callback_data="btn_bmb_themed_hub"))
    bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)

# --- QADAMLI DINAMIK YUKLANISH ANIMATSIYASI ---
def dynamic_ai_delivery(chat_id, prompt_text, user_id, category_tag):
    if check_security_violation(prompt_text):
        bot.send_message(chat_id, SECURITY_WARNING, parse_mode="Markdown")
        return

    status_msg = bot.send_message(chat_id, "⏳ *Manbalar va akademik adabiyotlar tahlil qilinmoqda...*", parse_mode="Markdown")
    time.sleep(1.2)
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🔍 *DTS va OAK mezonlari bo'yicha qoliplashmoqda...*",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    time.sleep(1.2)
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="✨ *Ilmiy xulosa va tipografik matn tayyorlanmoqda...*",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    try:
        raw_result = generate_ai_content(prompt_text)
        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass

        deliver_styled_response(chat_id, user_id, raw_result, category_tag)
    except Exception as e:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ Xatolik yuz berdi: {e}")
        except Exception:
            bot.send_message(chat_id, f"❌ Xatolik yuz berdi: {e}")

def deliver_styled_response(chat_id, user_id, text, category_tag):
    is_admin = (int(user_id) == int(ADMIN_ID))

    styled_text = (
        "╭── 💎 **ILMIY-METODIK EKSPERT XULOSASI** ──╮\n\n"
        f"**>** {text.strip()}\n\n"
        "╰──────────────────────────────────────────╯\n"
        f"🏛 **Rasmiy kanal:** `{CHANNEL_USERNAME}`"
    )

    if is_admin:
        post_id = f"post_{int(time.time())}_{random.randint(100, 999)}"
        ADMIN_POST_STORAGE[post_id] = text

        markup = tele_types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            tele_types.InlineKeyboardButton(text="📢 Kanalga yuborish", callback_data=f"send_chan_{post_id}"),
            tele_types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{post_id}")
        )
        markup.add(tele_types.InlineKeyboardButton(text="📤 Ulashish", switch_inline_query="Ilmiy xulosa"))

        bot.send_message(
            user_id,
            f"{styled_text}\n\n━━━━━━━━━━━━━━━━━━━━\n👑 **Admin:** Ushbu materialni kanalga e'lon qilasizmi?",
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        markup = tele_types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            tele_types.InlineKeyboardButton(text="🔄 Yangi tahlil", callback_data=f"retry_{category_tag}"),
            tele_types.InlineKeyboardButton(text="📤 Do'stlarga ulashish", switch_inline_query=f"{category_tag} tahlili")
        )
        markup.add(
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            )
        )
        bot.send_message(chat_id, styled_text, parse_mode="Markdown", reply_markup=markup)

# --- MAJBURIY OBUNA ---
def is_subscribed(user_id):
    try:
        if int(user_id) == int(ADMIN_ID):
            return True
    except Exception:
        pass

    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return chat_member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

def send_subscription_prompt(chat_id):
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(
            text="✨ Rasmiy kanalga a'zo bo'lish", 
            url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        ),
        tele_types.InlineKeyboardButton(
            text="🔄 Obunani tasdiqlash", 
            callback_data="check_sub"
        )
    )
    matn = (
        "╭─── 🏛 **ILMIY-METODIK HAMJAMIYAT** ───╮\n\n"
        "AI-Tilshunos xizmatlaridan to'liq va limitsiz foydalanish "
        "uchun rasmiy ta'limiy kanalimizga obuna bo'ling:\n\n"
        f"👉 **Kanal:** {CHANNEL_USERNAME}\n\n"
        "Obuna bo'lgach, quyidagi tugma orqali tasdiqlang.\n"
        "╰─────────────────────────────────────╯"
    )
    bot.send_message(chat_id, matn, parse_mode="Markdown", reply_markup=markup)

# --- GEMINI SISTEMA KO'RSATMASI ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi OAK eksperti, filolog-matnshunos olim va BMB (DTM) "
    "hamda umumta'lim maktablari bo'yicha oliy toifali bosh metodistsiz.\n\n"
    "QAT'IY TALAB (MAQOLA VA TEZIS BO'YICHA):\n"
    "Foydalanuvchiga HECH QACHON TAYYOR MATN YOZMANG! Faqat mustaqil yozishi uchun: "
    "puxta ilmiy reja, ilmiy apparat, metodologiya va adabiyotlar yo'nalishini bering.\n\n"
    "QAT'IY TAQIQLAR:\n"
    "1. Diniy mazmundagi har qanday aqidaviy bahslar, amallar va fatvolar man etiladi.\n"
    "2. Amaldagi davlat boshqaruvi, davlat rahbari va amaldorlar shaxsi haqidagi ma'lumotlar taqiqlanadi.\n"
    "3. Tibbiy va huquqiy maslahatlar mutlaqo berilmaydi.\n"
    "4. Ekstremizm, axloqsizlik va buzg'unchilik 100% rad etiladi.\n\n"
    "HIKMAT VA MOTIVATSIYA TALABI:\n"
    "Fikrlar mutlaqo sun'iy ravishda o'ylab topilmasin! Faqat berilgan tarixiy davrning nodir adabiy manbalaridan, "
    "mutafakkir va allomalarining haqiqiy asarlaridan keltirilib, aniq kitob nomi va beti/bobi ilmiy asosda berilsin."
)

def generate_ai_content(prompt_text):
    if check_security_violation(prompt_text):
        return SECURITY_WARNING

    full_prompt = (
        f"{prompt_text}\n\n"
        "Talablar: Telegram Markdown formatida, ko'rkam sarlavhalar va ilmiy uslubda bo'lsin. "
        "Oxirida '📚 Manba:' keltirilsin."
    )
    models = ["gemini-3.6-flash"]
    last_error = ""
    for model_name in models:
        for attempt in range(3):
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.4
                    )
                )
                if response and response.text:
                    return response.text.strip() + IMZO
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                    time.sleep(3)
                    continue
                elif "503" in last_error or "UNAVAILABLE" in last_error:
                    time.sleep(2)
                    continue
                else:
                    break
    raise Exception(f"AI Xatolik tafsiloti: {last_error[:300]}")

# --- QUIZ TEST BATCH GENERATORI ---
def generate_quiz_batch(prompt_spec, count=30):
    models = ["gemini-3.6-flash"]
    last_error = ""
    for model_name in models:
        for attempt in range(3):
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt_spec,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.75
                    )
                )
                raw = response.text.strip()
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                questions = json.loads(raw)
                if isinstance(questions, list) and len(questions) >= 10:
                    return questions[:count]
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                    time.sleep(3)
                    continue
                elif "503" in last_error or "UNAVAILABLE" in last_error:
                    time.sleep(2)
                    continue
                else:
                    break
    raise Exception(f"Test shakllantirishda xatolik: {last_error[:300]}")

def get_themed_bmb_questions(theme_name):
    seed = random.randint(10000, 99999)
    prompt = (
        f"O'zbekiston Respublikasi BMB (DTM) standarti va amaldagi 5-11-sinf Ona tili va adabiyot darsliklari asosida "
        f"aynan '{theme_name}' mavzusi bo'yicha TO'LIQ 30 TA takrorlanmas, original Quiz test tuzing (Seed #{seed}).\n\n"
        "Qoidalari:\n"
        "1. Diniy, siyosiy, tibbiy yoki huquqiy mavzular mutlaqo bo'lmasin.\n"
        "2. Har bir savol aniq, adabiy tilda bo'lsin.\n"
        "Faqat quyidagi JSON formatida javob bering:\n"
        "[\n"
        "  {\n"
        '    "question": "Savol matni (maks 250 belgi)",\n'
        '    "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '    "correct_option_id": 0,\n'
        '    "explanation": "Qisqa izoh va darslik manbasi (maks 180 belgi)"\n'
        "  }\n"
        "]\n"
        "DIQQAT: 30 ta savol obyekti bo'lsin. Variantlar uzunligi 95 belgidan oshmasin."
    )
    return generate_quiz_batch(prompt, 30)

def get_attestation_questions():
    seed = random.randint(10000, 99999)
    prompt = (
        "Maktabgacha va maktab ta'limi vazirligi pedagoglar attestatsiyasi rasmiy spetsifikatsiyasi asosida "
        f"Ona tili va adabiyot fani o'qituvchilari uchun TO'LIQ 40 TA unikal test tuzing (Seed #{seed}).\n\n"
        "TAQSIMOTI:\n"
        "- Y1 (Bilish darajasi - qoida, atama, nazariya): 15 ta savol;\n"
        "- Y2 (Qo'llash darajasi - tahlil, sintaktik/fonetik parchalash): 15 ta savol;\n"
        "- Y3 (Mulohaza va metodika - matn teranligi, muammoli metodik vaziyat): 10 ta savol.\n\n"
        "Savol sarlavhasida darajani ko'rsating (Masalan: [Y1], [Y2], [Y3]).\n"
        "Faqat JSON formatida javob bering:\n"
        "[\n"
        "  {\n"
        '    "question": "[Y1] Savol matni",\n'
        '    "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '    "correct_option_id": 0,\n'
        '    "explanation": "Metodik asos va darslik manbasi"\n'
        "  }\n"
        "]\n"
        "DIQQAT: Ro'yxatda 40 ta savol bo'lsin. Variantlar 95 belgidan oshmasin."
    )
    return generate_quiz_batch(prompt, 40)

# --- ISHTIROKCHILAR JAVOBLARINI TUTISH ---
@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    poll_id = poll_answer.poll_id
    poll_info = POLL_CORRECT_MAP.get(poll_id)
    if not poll_info:
        return

    chat_id = poll_info["chat_id"]
    correct_opt = poll_info["correct_option_id"]
    chosen_opt = poll_answer.option_ids[0]

    user = poll_answer.user
    u_id = user.id
    u_name = user.first_name or "Ishtirokchi"

    if chat_id in ACTIVE_QUIZ_TRACKER:
        scores = ACTIVE_QUIZ_TRACKER[chat_id]["scores"]
        if u_id not in scores:
            scores[u_id] = {"name": u_name, "correct": 0}
        
        if chosen_opt == correct_opt:
            scores[u_id]["correct"] += 1

# --- TEST JARAYONINI BOSHQARISH SIKLI ---
def run_interactive_quiz_loop(target_chat_id, questions, duration_per_q, title):
    total_q = len(questions)
    is_channel = str(target_chat_id).startswith("@")
    is_anon = True if is_channel else False

    start_time = time.time()
    ACTIVE_QUIZ_TRACKER[target_chat_id] = {
        "scores": {},
        "total_q": total_q
    }

    bot.send_message(
        target_chat_id,
        f"🏁 **DIQQAT, {title.upper()} BOSHLANDI!**\n\n"
        f"▫️ Jami savollar: `{total_q} ta`\n"
        f"▫️ Har bir savolga ajratilgan vaqt: `⏳ {duration_per_q} soniya`\n"
        f"▫️ Rasmiy kanal: `{CHANNEL_USERNAME}`\n\n"
        "Har bir to'g'ri javob qayd etiladi va yakunda **REYTING JADVALI** e'lon qilinadi!",
        parse_mode="Markdown"
    )
    time.sleep(2)

    for idx, q_data in enumerate(questions, 1):
        question_text = f"[{idx}/{total_q}] ⏳ {duration_per_q}s | {q_data['question']}"
        if len(question_text) > 295:
            question_text = question_text[:292] + "..."

        options = [str(opt)[:95] for opt in q_data["options"][:4]]
        if len(options) < 2:
            options = ["A varianti", "B varianti"]

        correct_id = int(q_data.get("correct_option_id", 0))
        if correct_id < 0 or correct_id >= len(options):
            correct_id = 0

        explanation = f"{q_data.get('explanation', '')}\n👉 {CHANNEL_USERNAME}"[:195]

        try:
            poll_msg = bot.send_poll(
                chat_id=target_chat_id,
                question=question_text,
                options=options,
                type="quiz",
                correct_option_id=correct_id,
                explanation=explanation,
                is_anonymous=is_anon,
                open_period=duration_per_q
            )
            POLL_CORRECT_MAP[poll_msg.poll.id] = {
                "chat_id": target_chat_id,
                "correct_option_id": correct_id
            }
        except Exception as err:
            print(f"Poll jo'natish xatosi: {err}")
            try:
                poll_msg = bot.send_poll(
                    chat_id=target_chat_id,
                    question=question_text,
                    options=options,
                    type="quiz",
                    correct_option_id=correct_id,
                    is_anonymous=True
                )
            except Exception:
                pass

        time.sleep(duration_per_q + 2)

    tracker = ACTIVE_QUIZ_TRACKER.pop(target_chat_id, None)
    duration_total = int(time.time() - start_time)

    if is_channel:
        finish_msg = (
            f"╔════════════════════════════════╗\n"
            f"  🏆 **{title.upper()} YAKUNLANDI!**\n"
            f"╚════════════════════════════════╝\n\n"
            "Kanalda o'tkazilgan test muvaffaqiyatli yakunlandi.\n"
            "💡 *Telegram qoidasiga ko'ra kanallardagi ovoz berish anonim bo'ladi. "
            "Individual reyting va o'rningizni bilish uchun testni botda yoki o'z guruhingizda ishlang!*\n\n"
            f"Rasmiy manba: `{CHANNEL_USERNAME}`"
        )
        bot.send_message(target_chat_id, finish_msg, parse_mode="Markdown")
    else:
        scores = tracker["scores"] if tracker else {}
        results = load_data(RESULTS_FILE)

        if scores:
            for uid, info in scores.items():
                results[str(uid)] = {
                    "name": info["name"],
                    "correct": info["correct"],
                    "duration": duration_total,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
            save_data(RESULTS_FILE, results)

            sorted_participants = sorted(scores.items(), key=lambda x: x[1]["correct"], reverse=True)
            leaderboard_text = ""
            for rank, (uid, info) in enumerate(sorted_participants, 1):
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"`#{rank}`"
                perc = round((info["correct"] / total_q) * 100, 1)
                leaderboard_text += f"{medal} **{info['name']}** — `{info['correct']}/{total_q}` to'g'ri (`{perc}%`)\n"

            finish_msg = (
                f"╔════════════════════════════════╗\n"
                f"  🏆 **{title.upper()} REYTINGI**\n"
                f"╚════════════════════════════════╝\n\n"
                f"👥 Jami ishtirokchilar: `{len(sorted_participants)} nafar`\n"
                f"📊 Savollar soni: `{total_q} ta`\n\n"
                "🏅 **ISHTIROKCHILARNING EGALLAGAN O'RINLARI:**\n"
                f"{leaderboard_text}\n"
                "────────────────────────────────\n"
                f"✨ Rasmiy filologik kanalimiz: `{CHANNEL_USERNAME}`"
            )
        else:
            finish_msg = (
                f"╔════════════════════════════════╗\n"
                f"  🏆 **{title.upper()} YAKUNLANDI!**\n"
                f"╚════════════════════════════════╝\n\n"
                "Test yakunlandi. Hech bir ishtirokchi javob belgilamadi.\n\n"
                f"Rasmiy kanal: `{CHANNEL_USERNAME}`"
            )

        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi (Mini-App)", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            ),
            tele_types.InlineKeyboardButton(text="📤 Natijani ulashish", switch_inline_query="Mening test natijam")
        )
        bot.send_message(target_chat_id, finish_msg, parse_mode="Markdown", reply_markup=markup)

# --- 3 KISHI «TAYYORMAN» TIZIMI ---
def setup_match_lobby(chat_id, questions, duration_per_q, title):
    match_id = f"m_{int(time.time())}_{random.randint(100, 999)}"
    READY_MATCHES[match_id] = {
        "chat_id": chat_id,
        "questions": questions,
        "duration": duration_per_q,
        "title": title,
        "ready_users": {},
        "started": False
    }

    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(text="✋ Men tayyorman (0/3)", callback_data=f"rdy_{match_id}"),
        tele_types.InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
    )

    announcement = (
        f"╔════════════════════════════════╗\n"
        f"  🧠 **{title.upper()}**\n"
        f"╚════════════════════════════════╝\n\n"
        f"▫️ Savollar soni: `{len(questions)} ta`\n"
        f"▫️ Vaqt me'yori: Har bir savolga `⏳ {duration_per_q} soniya`\n"
        f"▫️ Manzil: `{CHANNEL_USERNAME}`\n\n"
        "⚠️ **Qoida:** Test start olishi uchun kamida **3 nafar ishtirokchi** "
        "«Men tayyorman» tugmasini bosishi lozim!"
    )
    bot.send_message(chat_id, announcement, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rdy_"))
def callback_match_lobby(call):
    match_id = call.data.replace("rdy_", "")
    m = READY_MATCHES.get(match_id)
    if not m or m["started"]:
        bot.answer_callback_query(call.id, "Test allaqachon boshlangan yoki yakunlangan.", show_alert=True)
        return

    uid = call.from_user.id
    uname = call.from_user.first_name or "Ishtirokchi"

    if uid in m["ready_users"]:
        bot.answer_callback_query(call.id, "Siz tayyorsiz! Boshqalarni kutyapmiz...", show_alert=False)
        return

    m["ready_users"][uid] = uname
    count = len(m["ready_users"])
    bot.answer_callback_query(call.id, f"Qabul qilindi! ({count}/3)")

    if count < 3:
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text=f"✋ Men tayyorman ({count}/3)", callback_data=f"rdy_{match_id}"),
            tele_types.InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
        )
        try:
            bot.edit_message_reply_markup(chat_id=m["chat_id"], message_id=call.message.message_id, reply_markup=markup)
        except Exception:
            pass
    else:
        m["started"] = True
        names = ", ".join(list(m["ready_users"].values())[:5])
        try:
            bot.edit_message_text(
                chat_id=m["chat_id"],
                message_id=call.message.message_id,
                text=f"🎉 **Yetarli ishtirokchilar yig'ildi! (Tayyorlar: {names})**\n\n🚀 Test 5 soniyadan so'ng start oladi...",
                parse_mode="Markdown"
            )
        except Exception:
            pass

        time.sleep(5)
        threading.Thread(
            target=run_interactive_quiz_loop,
            args=(m["chat_id"], m["questions"], m["duration"], m["title"]),
            daemon=True
        ).start()

# --- TEST TAYYOR BO'LGANDA TANLOV MENYUSI ---
def offer_quiz_dispatch(chat_id, user_id, questions, duration_per_q, title):
    quiz_id = f"qz_{int(time.time())}_{random.randint(100, 999)}"
    PENDING_QUIZZES[quiz_id] = {
        "questions": questions,
        "duration": duration_per_q,
        "title": title
    }

    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    if int(user_id) == int(ADMIN_ID):
        markup.add(
            tele_types.InlineKeyboardButton(text="📢 Kanalga e'lon qilish (@onatilidanyordam)", callback_data=f"act_chan_{quiz_id}"),
            tele_types.InlineKeyboardButton(text="🤖 Botning o'zida ishlash (Darhol)", callback_data=f"act_bot_{quiz_id}")
        )
        bot.send_message(
            chat_id,
            f"👑 **Hurmatli Admin!**\n\n**{title}** muvaffaqiyatli shakllantirildi.\nTestni qayerda o'tkazmoqchisiz?",
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        markup.add(
            tele_types.InlineKeyboardButton(text="🤖 Botning o'zida yakkaxon ishlash (Darhol)", callback_data=f"act_bot_{quiz_id}"),
            tele_types.InlineKeyboardButton(text="👥 O'z guruhimga tashlash (Bellashuv)", callback_data=f"act_grpinfo_{quiz_id}")
        )
        bot.send_message(
            chat_id,
            f"🎉 **{title}** muvaffaqiyatli tayyorlandi!\nQayerda test ishlamoqchisiz? Tanlang:",
            parse_mode="Markdown",
            reply_markup=markup
        )

# --- TEST TANLOV CALLBACKLARI ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("act_chan_", "act_bot_", "act_grpinfo_")))
def callback_quiz_routing(call):
    data = call.data
    
    if data.startswith("act_chan_"):
        if int(call.from_user.id) != int(ADMIN_ID):
            bot.answer_callback_query(call.id, "Faqat admin uchun!", show_alert=True)
            return
        quiz_id = data.replace("act_chan_", "")
        q_data = PENDING_QUIZZES.get(quiz_id)
        if not q_data:
            bot.answer_callback_query(call.id, "Test ma'lumoti eskirgan.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Kanalga yuborilmoqda...")
        setup_match_lobby(CHANNEL_USERNAME, q_data["questions"], q_data["duration"], q_data["title"])
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ **{q_data['title']}** rasmiy {CHANNEL_USERNAME} kanaliga e'lon qilindi!\nKanalda 3 kishi «Tayyorman»ni bosgach test boshlanadi."
        )

    elif data.startswith("act_bot_"):
        quiz_id = data.replace("act_bot_", "")
        q_data = PENDING_QUIZZES.get(quiz_id)
        if not q_data:
            bot.answer_callback_query(call.id, "Test ma'lumoti eskirgan.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Test boshlanmoqda!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        threading.Thread(
            target=run_interactive_quiz_loop,
            args=(call.message.chat.id, q_data["questions"], q_data["duration"], q_data["title"]),
            daemon=True
        ).start()

    elif data.startswith("act_grpinfo_"):
        bot.answer_callback_query(call.id)
        info_text = (
            "╭── 👥 **TESTNI GURUHINGIZDA O'TKAZISH TARTIBI** ──╮\n\n"
            "1. Botingizni sinf yoki abituriyent guruhingizga qo'shing.\n"
            "2. Botga guruhda **Admin** huquqini bering (so'rovnoma yuborishi uchun).\n"
            "3. Guruh chatida `/quiz_start` buyrug'ini yuboring.\n"
            "4. Bot guruhga e'lon tashlaydi va 3 kishi «Men tayyorman» tugmasini bosishi bilanoq test start oladi!\n"
            "5. Yakunda butun guruh reytingi e'lon qilinadi.\n\n"
            f"Rasmiy kanal: `{CHANNEL_USERNAME}`\n"
            "╰──────────────────────────────────────────╯"
        )
        bot.send_message(call.message.chat.id, info_text, parse_mode="Markdown")

# --- GURUHDAN /quiz_start BUYRUG'I BERILGANDA ---
@bot.message_handler(commands=['quiz_start'])
def cmd_quiz_start_group(message):
    chat_type = message.chat.type
    if chat_type in ['group', 'supergroup']:
        bot.reply_to(
            message, 
            "⏳ *Guruh uchun BMB 30 talik test paketi shakllanmoqda... Iltimos kuting!*", 
            parse_mode="Markdown"
        )
        try:
            bmb_num = get_next_quiz_number("bmb_30")
            quiz_title = f"№{bmb_num} BMB 30 talik test (Guruh Bellashuvi)"
            questions = get_themed_bmb_questions("5-11-sinf barcha darsliklari")
            setup_match_lobby(message.chat.id, questions, duration_per_q=30, title=quiz_title)
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")
    else:
        bot.reply_to(message, "Ushbu buyruq faqat Telegram guruhlarida ishlaydi.")

# --- ADMIN KANALGA YUBORISH / BEKOR QILISH HANDLERI ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("send_chan_", "cancel_")))
def callback_admin_approval(call):
    if int(call.from_user.id) != int(ADMIN_ID):
        bot.answer_callback_query(call.id, "Faqat bot administratori uchun!")
        return

    data = call.data
    if data.startswith("send_chan_"):
        post_id = data.replace("send_chan_", "")
        content = ADMIN_POST_STORAGE.get(post_id)
        if content:
            try:
                bot.send_message(CHANNEL_USERNAME, content, parse_mode="Markdown")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"{call.message.text}\n\n✅ **Kanalga muvaffaqiyatli e'lon qilindi!**"
                )
                bot.answer_callback_query(call.id, "Kanalga joylandi!")
            except Exception as e:
                bot.answer_callback_query(call.id, f"Xatolik: {e}", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "Matn eskirgan.", show_alert=True)

    elif data.startswith("cancel_"):
        post_id = data.replace("cancel_", "")
        ADMIN_POST_STORAGE.pop(post_id, None)
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"{call.message.text}\n\n❌ **Kanalga yuborish bekor qilindi.**"
            )
            bot.answer_callback_query(call.id, "Bekor qilindi.")
        except Exception:
            pass

# --- ADMIN: KUN HIKMATI VA MOTIVATSIYA GENERATSIYASI ---
def get_verified_didactic_content(content_type="hikmat"):
    chosen_epoch = random.choice(HISTORICAL_EPOCHS)
    seed = random.randint(1000, 99999)

    if content_type == "hikmat":
        prompt = (
            f"Siz o'zbek adabiyoti tarixi va manbashunoslik bo'yicha yuksak eksiz.\n"
            f"Aynan quyidagi adabiy-tarixiy davrga mansub durdona asarlardan 1 ta didaktik hikmatni keltiring:\n"
            f"🏛 **Davr:** {chosen_epoch['epoch']}\n"
            f"📜 **Tavsiya etiladigan manbalar:** {chosen_epoch['sources']}\n"
            f"Identifikator: #{seed}\n\n"
            "QAT'IY TALABLAR:\n"
            "1. Mazkur hikmat ilm, odob, qanoat, vaqt qadri, adolat yoki donolik xususida bo'lsin.\n"
            "2. Sun'iy ravishda to'qilmasin! Haqiqiy kitob, asar, doston yoki manbadan aniq iqtibos oling.\n"
            "3. Diniy, siyosiy, tibbiy yoki huquqiy mavzulardan 100% chetlashing.\n\n"
            "Qat'iy format:\n"
            "🏛 **Davr:** [Tanlangan davr nomi]\n\n"
            "[HIKMAT MATNI]\n\n"
            "📚 Aniq manba: [Muallif, asar nomi, bob yoki bayt ko'rsatkichi]"
        )
    else:
        prompt = (
            f"Siz ma'rifiy meros va milliy taraqqiyot bo'yicha mutaxassis olimsiz.\n"
            f"Aynan quyidagi davr mutafakkirlari, adiblari yoki allomalarining asarlaridan insonni ilm olishga, "
            f"o'qish-o'rganishga, shaxsiy rivojlanishga va g'ayrat ko'rsatishga undovchi 1 ta ruhiy-motivatsion fikr keltiring:\n"
            f"🏛 **Davr:** {chosen_epoch['epoch']}\n"
            f"📜 **Tavsiya etiladigan manbalar:** {chosen_epoch['sources']}\n"
            f"Identifikator: #{seed}\n\n"
            "QAT'IY TALABLAR:\n"
            "1. Sun'iy to'qilmasin! Berilgan davr allomalarining haqiqiy risola, doston, roman yoki maqolalaridan olinsin.\n"
            "2. Diniy, siyosiy, tibbiy yoki huquqiy mavzulardan mutlaqo chetlashing.\n\n"
            "Qat'iy format:\n"
            "🏛 **Davr:** [Tanlangan davr nomi]\n\n"
            "[MOTIVATSIYA MATNI]\n\n"
            "📚 Aniq manba: [Muallif, asar nomi, chop etilgan nashr yoki sahifa ko'rsatkichi]"
        )

    response = ai_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7
        )
    )
    return response.text.strip()

@bot.callback_query_handler(func=lambda call: call.data.startswith("pub_"))
def callback_publish_quote(call):
    if int(call.from_user.id) != int(ADMIN_ID):
        return
    
    post_id = call.data.replace("pub_", "")
    text_data = ADMIN_POST_STORAGE.get(post_id)
    if not text_data:
        bot.answer_callback_query(call.id, "Matn eskirgan.", show_alert=True)
        return

    clean_text = text_data.split("📚 Aniq manba:")[0].strip()
    channel_post = f"{clean_text}\n\n───────────────\n🌟 **Rasmiy kanal:** `{CHANNEL_USERNAME}`"

    try:
        bot.send_message(CHANNEL_USERNAME, channel_post, parse_mode="Markdown")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"{call.message.text}\n\n✅ **Kanalga manbasiz muvaffaqiyatli joylandi!**"
        )
        bot.answer_callback_query(call.id, "Kanalga joylandi!")
    except Exception as e:
        bot.answer_callback_query(call.id, f"Xatolik: {e}", show_alert=True)

# --- INLINE KNOPKALARNING HANDLERLARI ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("btn_", "theme_", "seltheme_")))
def callback_button_actions(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    data = call.data

    if data == "btn_bmb_themed_hub":
        send_themed_test_hub(cid)

    elif data == "theme_open_catalog":
        send_theme_catalog(cid)

    elif data == "theme_custom_input":
        msg = bot.send_message(
            cid, 
            "✍️ **Erkin mavzu bo'yicha test:**\n\n"
            "Qaysi darslik mavzusidan 30 talik test tuzmoqchisiz? Yozib yuboring:\n"
            "👉 *Masalan: «Qo'shma gap turlari», «Sifatdosh va uning vazifalari», «Boburnoma fitonimlari»*", 
            parse_mode="Markdown"
        )
        def start_custom_theme(m):
            theme = m.text.strip()
            quiz_title = f"«{theme}» mavzusi bo'yicha test (30 ta)"
            bot.send_message(cid, f"⏳ *«{theme}» bo'yicha test shakllanmoqda... Har bir savolga ⏳ 30 soniya!*", parse_mode="Markdown")
            try:
                questions = get_themed_bmb_questions(theme)
                offer_quiz_dispatch(cid, uid, questions, duration_per_q=30, title=quiz_title)
            except Exception as e:
                bot.send_message(cid, f"❌ Xatolik: {e}")
        bot.register_next_step_handler(msg, start_custom_theme)

    elif data.startswith("seltheme_"):
        cat_key = data.replace("seltheme_", "")
        cat_info = THEME_CATALOG.get(cat_key)
        if cat_info:
            quiz_title = f"{cat_info['title']} (30 ta)"
            bot.send_message(cid, f"⏳ *{cat_info['title']} bo'yicha 30 talik test tuzilmoqda... Har bir savolga ⏳ 30 soniya!*", parse_mode="Markdown")
            try:
                questions = get_themed_bmb_questions(cat_info["prompt"])
                offer_quiz_dispatch(cid, uid, questions, duration_per_q=30, title=quiz_title)
            except Exception as e:
                bot.send_message(cid, f"❌ Xatolik: {e}")

    elif data == "btn_gazal":
        msg = bot.send_message(cid, "✍️ Badiiy tahlil qilmoqchi bo'lgan mumtoz baytingizni yuboring:")
        p = "Ushbu baytni badiiy tahlil qiling: '{input}'. San'atlari va so'zlar sharhini bering."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "gazal"))

    elif data == "btn_aruz":
        msg = bot.send_message(cid, "✍️ Aruzini aniqlamoqchi bo'lgan baytingizni yuboring:")
        p = "Ushbu baytni aruz tizimi bo'yicha tahlil qiling (hijolar, ruknlar, bahr nomi): '{input}'"
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "aruz"))

    elif data == "btn_qadim":
        msg = bot.send_message(cid, "✍️ Qaysi tarixiy yoki arxaik so'z kerak? Yozing:")
        p = "'{input}' so'zini qadimgi turkiy manbalar asosida filologik tahlil qiling."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "qadimgi_til"))

    elif data == "btn_etim":
        msg = bot.send_message(cid, "🔍 Etimologiyasini bilmoqchi bo'lgan so'zingizni yozing:")
        p = "'{input}' so'zining tarixiy ildizi va etimologiyasini tushuntiring."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "etimologiya"))

    elif data == "btn_konspekt":
        msg = bot.send_message(cid, "📋 Qaysi sinf va mavzu bo'yicha dars ishlanmasi kerak? Yozib yuboring:")
        p = "Umumta'lim maktabi uchun '{input}' mavzusida to'liq 45 daqiqalik dars ishlanmasi (konspekt) tuzing."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "konspekt"))

    elif data == "btn_metod":
        msg = bot.send_message(cid, "🎯 Qaysi mavzu uchun interfaol metod kerak? Yozing:")
        p = "'{input}' mavzusi uchun zamonaviy interfaol metod ishlab chiqing."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "metod"))

    elif data == "btn_attest":
        bot.send_message(cid, "⏳ *Attestatsiya spetsifikatsiyasi bo'yicha 40 ta Y1, Y2, Y3 testlari shakllanmoqda...*", parse_mode="Markdown")
        try:
            att_num = get_next_quiz_number("attestation")
            quiz_title = f"№{att_num} Attestatsiya Y1, Y2, Y3 testi"
            questions = get_attestation_questions()
            offer_quiz_dispatch(cid, uid, questions, duration_per_q=40, title=quiz_title)
        except Exception as e:
            bot.send_message(cid, f"❌ Xatolik: {e}")

    elif data == "btn_esse":
        msg = bot.send_message(cid, "📝 Esse mavzusi va matnini to'liq yuboring:")
        p = "Ushbu esse matnini BMB 50 ballik mezoni bo'yicha tekshiring: '{input}'"
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "esse"))

    elif data == "btn_izoh":
        msg = bot.send_message(cid, "📖 Izohini yoki imlosini bilmoqchi bo'lgan so'zingizni yozing:")
        p = "O'zbek tilining izohli lug'ati va imlo qoidalari asosida '{input}' so'zini to'liq sharhlang."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "izoh_imlo"))

    elif data == "btn_bmb_gen":
        bot.send_message(cid, "⏳ *BMB standarti bo'yicha 30 talik test shakllanmoqda...*", parse_mode="Markdown")
        try:
            bmb_num = get_next_quiz_number("bmb_30")
            quiz_title = f"№{bmb_num} BMB 30 talik test"
            questions = get_themed_bmb_questions("5-11-sinf barcha bo'limlari")
            offer_quiz_dispatch(cid, uid, questions, duration_per_q=30, title=quiz_title)
        except Exception as e:
            bot.send_message(cid, f"❌ Xatolik: {e}")

    elif data == "btn_maqola":
        msg = bot.send_message(cid, "✍️ Ilmiy tadqiqot mavzusini kiriting:")
        p = "OAK talablari asosida '{input}' mavzusida maqola yozish uchun REJA va METODIK KO'RSATMA bering. Tayyor matn bermang."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "maqola"))

    elif data == "btn_tezis":
        msg = bot.send_message(cid, "✍️ Tezis mavzusini kiriting:")
        p = "Konferensiya uchun '{input}' mavzusida tezis yozish bo'yicha REJA va YO'RIQNOMA bering. Tayyor matn bermang."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "tezis"))

    bot.answer_callback_query(call.id)

# --- RETRY CALLBACK HANDLER ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("retry_"))
def callback_retry(call):
    tag = call.data.replace("retry_", "")
    bot.answer_callback_query(call.id, "Yangi so'rovni kiriting:")
    msg = bot.send_message(call.message.chat.id, "✍️ Yangi mavzu yoki tahlil matnini yuboring:")
    prompt_map = {
        "gazal": "Ushbu baytni badiiy tahlil qiling: '{input}'. San'atlari va so'zlar sharhini bering.",
        "aruz": "Ushbu baytni aruz tizimi bo'yicha tahlil qiling: '{input}'",
        "konspekt": "Umumta'lim maktabi uchun '{input}' mavzusida to'liq 45 daqiqalik dars ishlanmasi tuzing.",
        "metod": "'{input}' mavzusi uchun zamonaviy interfaol metod ishlab chiqing.",
        "esse": "Ushbu esse matnini BMB 50 ballik mezoni bo'yicha tekshiring: '{input}'",
        "maqola": "OAK talablari asosida '{input}' mavzusida maqola yozish uchun REJA va METODIK KO'RSATMA bering."
    }
    p = prompt_map.get(tag, "'{input}' bo'yicha ilmiy tahlil bering.")
    bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(call.message.chat.id, p.format(input=m.text), call.from_user.id, tag))

# --- INLINE QUERY HANDLER ---
@bot.inline_handler(lambda query: True)
def default_inline_query(inline_query):
    try:
        r = tele_types.InlineQueryResultArticle(
            id='1',
            title="AI Tilshunos & Metodist Platformasi",
            description="BMB testlari, OAK maqolalari va dars konspektlari tizimi",
            input_message_content=tele_types.InputTextMessageContent(
                message_text=(
                    "🏛 **AI TILSHUNOS & METODIST PORTALI**\n\n"
                    "Ona tili, adabiyot va pedagogika sohasidagi sun'iy intellekt yordamchisi.\n\n"
                    "▫️ BMB 30 talik testlar va jonli reyting;\n"
                    "▫️ Attestatsiya Y1, Y2, Y3 testlari;\n"
                    "▫️ OAK maqola va dars konspektlari konstruktori.\n\n"
                    f"👉 Botdan foydalanish: @aitilshunosbot\n"
                    f"👉 Rasmiy kanal: {CHANNEL_USERNAME}"
                ),
                parse_mode="Markdown"
            )
        )
        bot.answer_inline_query(inline_query.id, [r])
    except Exception as e:
        print(f"Inline query xatosi: {e}")

# --- START BUYRUG'I ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_user(message.from_user)

    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    user_name = message.from_user.first_name or "Foydalanuvchi"
    text = (
        f"╭──── ✨ **Assalomu alaykum, {user_name}!** ────╮\n\n"
        "🏛 **AI TILSHUNOS & METODIST (v10.5)** portaliga xush kelibsiz!\n\n"
        "Quyidagi asosiy yo'nalishlardan birini tanlang:\n\n"
        "🎓 **Talabalar uchun:** Mumtoz meros, aruz, qadimgi til va etimologiya\n"
        "👨‍🏫 **O'qituvchilar uchun:** Konspektlar, metodlar va Attestatsiya testlari\n"
        "🎒 **Abituriyentlar uchun:** Esse, O'TIL, imlo, BMB va Mavzuli testlar\n"
        "🔬 **Ilmiy izlanuvchilar uchun:** OAK maqola va tezis loyihalash\n\n"
        "👇 *Yo'nalishingizni tanlang:* \n"
        "╰─────────────────────────────────────╯"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data in ["check_sub"])
def callback_check_sub(call):
    save_user(call.from_user)
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "🎉 Obuna tasdiqlandi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

# --- ASOSIY MENYU XABARLARI ISHLOVCHISI ---
@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    save_user(message.from_user)

    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = message.text
    u_id = message.from_user.id
    is_admin = (int(u_id) == int(ADMIN_ID))

    if text == "🔙 Asosiy menyu":
        bot.send_message(message.chat.id, "📋 Asosiy toifalardan birini tanlang:", reply_markup=get_main_menu(u_id))
        return

    elif text == "🎓 Talabalar uchun":
        send_section_card(message.chat.id, "talaba")

    elif text == "👨‍🏫 O'qituvchilar uchun":
        send_section_card(message.chat.id, "oqituvchi")

    elif text == "🎒 Abituriyentlar uchun":
        send_section_card(message.chat.id, "abituriyent")

    elif text == "🔬 Ilmiy izlanuvchilar uchun":
        send_section_card(message.chat.id, "izlanuvchi")

    elif text == "📊 Boshqaruv & Statistika" and is_admin:
        users = load_data(USERS_FILE)
        results = load_data(RESULTS_FILE)
        ch_count = bot.get_chat_member_count(CHANNEL_USERNAME)

        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi (Mini-App)", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            )
        )

        bot.send_message(
            message.chat.id,
            f"📊 **Boshqaruv Paneli (Admin):**\n\n"
            f"▫️ Jami bot a'zolari: `{len(users)} nafar`\n"
            f"▫️ Test topshirganlar: `{len(results)} nafar`\n"
            f"▫️ Rasmiy kanal obunachilari: `{ch_count} nafar`\n"
            f"▫️ Xabar tarqatish: `/send matn`",
            parse_mode="Markdown",
            reply_markup=markup
        )

    elif text == "☀️ Kun hikmati (Admin)" and is_admin:
        bot.send_message(message.chat.id, "⏳ *Tarixiy davrlar bo'yicha yangi hikmat saralanmoqda...*", parse_mode="Markdown")
        try:
            hikmat_full = get_verified_didactic_content("hikmat")
            p_id = f"hik_{int(time.time())}"
            ADMIN_POST_STORAGE[p_id] = hikmat_full

            markup = tele_types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                tele_types.InlineKeyboardButton(text="📢 Kanalga joylash (Manbasiz)", callback_data=f"pub_{p_id}"),
                tele_types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{p_id}")
            )
            bot.send_message(
                message.chat.id,
                f"☀️ **KUN HIKMATI (ADMIN TEKSHIRUVI):**\n\n{hikmat_full}\n\n"
                f"💡 *Kanalga chiqarilsa manba qismi avtomatik olib tashlanadi va faqat {CHANNEL_USERNAME} imzosi qo'yiladi.*",
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xatolik: {e}")

    elif text == "⚡️ Motivatsiya (Admin)" and is_admin:
        bot.send_message(message.chat.id, "⏳ *Tarixiy davrlar bo'yicha ma'rifiy motivatsiya saralanmoqda...*", parse_mode="Markdown")
        try:
            motiv_full = get_verified_didactic_content("motiv")
            p_id = f"mot_{int(time.time())}"
            ADMIN_POST_STORAGE[p_id] = motiv_full

            markup = tele_types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                tele_types.InlineKeyboardButton(text="📢 Kanalga joylash (Manbasiz)", callback_data=f"pub_{p_id}"),
                tele_types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{p_id}")
            )
            bot.send_message(
                message.chat.id,
                f"⚡️ **MOTIVATSIYA (ADMIN TEKSHIRUVI):**\n\n{motiv_full}\n\n"
                f"💡 *Kanalga chiqarilsa manba qismi avtomatik olib tashlanadi va faqat {CHANNEL_USERNAME} imzosi qo'yiladi.*",
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xatolik: {e}")

    else:
        bot.send_message(message.chat.id, "Iltimos, menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu(u_id))

print("AI Tilshunos v10.5 (Theme Catalog Edition) faol ishga tushdi...")
bot.infinity_polling()

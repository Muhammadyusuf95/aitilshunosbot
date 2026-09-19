import os
import threading
import json
import random
import time
from datetime import datetime, timedelta
import sqlite3
import pytz
import requests
from flask import Flask, render_template_string
import telebot
from telebot import types as tele_types
from google import genai
from google.genai import types

# Alohida fayldagi 20 ta namunaviy esseni yuklab olamiz
try:
    from sample_essays import SAMPLE_ESSAYS
except ImportError:
    SAMPLE_ESSAYS = []

app = Flask(__name__)
RESULTS_FILE = "test_results.json"
USERS_FILE = "users.json"
COUNTERS_FILE = "quiz_counters.json"
BAZA_FILE = "baza.json"
DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            points INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_active TEXT,
            status TEXT DEFAULT 'active',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                old_users = json.load(f)
                for uid, udata in old_users.items():
                    cursor.execute("""
                        INSERT OR IGNORE INTO users (user_id, username, first_name, points, streak, last_active, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        int(uid),
                        udata.get("username", ""),
                        udata.get("first_name", ""),
                        udata.get("points", 0),
                        udata.get("streak", 1),
                        udata.get("last_active", ""),
                        udata.get("status", "active")
                    ))
            conn.commit()
        except Exception:
            pass
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

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

def load_local_knowledge_base(file_path=BAZA_FILE):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"JSON yuklashda xatolik: {e}")
            return None
    return None

WEBAPP_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>BMB Test Reytingi & Shaxsiy Kabinet</title>
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
    .header { text-align: center; margin-bottom: 20px; }
    .badge {
      display: inline-block; padding: 4px 12px; background: rgba(56, 189, 248, 0.15);
      color: var(--primary); border-radius: 999px; font-size: 12px; font-weight: 600; margin-bottom: 8px;
    }
    h1 { font-size: 20px; margin: 0 0 6px 0; }
    .sub { color: var(--text-dim); font-size: 13px; }
    .stats-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 18px; }
    .stat-card {
      background: var(--card); padding: 12px 6px; border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.05); text-align: center;
    }
    .stat-val { font-size: 16px; font-weight: bold; color: var(--primary); }
    .stat-lbl { font-size: 10px; color: var(--text-dim); margin-top: 2px; }
    .leaderboard {
      background: var(--card); border-radius: 16px; padding: 12px;
      border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .row { display: flex; align-items: center; padding: 10px 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.04); }
    .row:last-child { border-bottom: none; }
    .rank { width: 28px; font-weight: 700; font-size: 14px; }
    .rank-1 { color: #fbbf24; }
    .rank-2 { color: #94a3b8; }
    .rank-3 { color: #d97706; }
    .info { flex: 1; padding: 0 8px; }
    .name { font-size: 14px; font-weight: 600; }
    .details { font-size: 11px; color: var(--text-dim); }
    .score { font-weight: 700; color: var(--primary); font-size: 13px; text-align: right; }
  </style>
</head>
<body>
  <div class="header">
    <div class="badge">MILLIY SERTIFIKAT & BMB</div>
    <h1>🏆 Jonli Reyting & Darajalar</h1>
    <div class="sub">@onatilidanyordam hamjamiyati</div>
  </div>
  <div class="stats-grid">
    <div class="stat-card"><div class="stat-val">{{ total_users }}</div><div class="stat-lbl">A'zolar</div></div>
    <div class="stat-card"><div class="stat-val">{{ total_tested }}</div><div class="stat-lbl">Test topshirganlar</div></div>
    <div class="stat-card"><div class="stat-val">{{ active_streaks }}</div><div class="stat-lbl">🔥 Faol seriyalar</div></div>
  </div>
  <div class="leaderboard">
    {% for user in top_users %}
    <div class="row">
      <div class="rank rank-{{ user.rank }}">{{ user.rank_icon }}</div>
      <div class="info">
        <div class="name">{{ user.name }}</div>
        <div class="details">🔥 {{ user.streak }} kun seriya • {{ user.points }} ball</div>
      </div>
      <div class="score">{{ user.correct }}/30 to'g'ri<br><span style="font-size:10px; color:var(--text-dim); font-weight:normal;">⏳ {{ user.duration_str }}</span></div>
    </div>
    {% else %}
    <div style="text-align: center; padding: 20px; color: var(--text-dim); font-size: 13px;">Hozircha natijalar mavjud emas. Birinchi bo'lib test topshiring!</div>
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
    return "AI Tilshunos & Metodist v11.3 (Modular Edition) Faol!"

@app.route('/leaderboard')
def webapp_leaderboard():
    results = load_data(RESULTS_FILE)
    conn = get_db_connection()
    users_db = {str(row["user_id"]): dict(row) for row in conn.execute("SELECT * FROM users").fetchall()}
    conn.close()
    
    sorted_res = sorted(
        results.items(), 
        key=lambda x: (
            -x[1].get("correct", 0), 
            -users_db.get(str(x[0]), {}).get("points", 0),
            x[1].get("duration", 999999)
        )
    )[:25]
    
    top_list = []
    active_streak_count = sum(1 for u in users_db.values() if u.get("streak", 0) > 1)

    for idx, (uid, info) in enumerate(sorted_res, 1):
        icon = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"#{idx}"
        dur = info.get("duration", 0)
        dur_str = f"{dur//60}m {dur%60}s"
        u_record = users_db.get(str(uid), {})
        
        top_list.append({
            "rank": idx,
            "rank_icon": icon,
            "name": info.get("name", "Ishtirokchi"),
            "correct": info.get("correct", 0),
            "duration_str": dur_str,
            "streak": u_record.get("streak", 1),
            "points": u_record.get("points", 0)
        })

    return render_template_string(
        WEBAPP_HTML,
        total_users=len(users_db),
        total_tested=len(results),
        active_streaks=active_streak_count,
        top_users=top_list
    )

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

RENDER_APP_URL = "https://aitilshunosbot.onrender.com"

def keep_alive():
    while True:
        try:
            time.sleep(600)
            requests.get(RENDER_APP_URL)
        except Exception:
            pass

threading.Thread(target=keep_alive, daemon=True).start()

TELEGRAM_TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@onatilidanyordam"
CHANNEL_URL = "https://t.me/onatilidanyordam"
ADMIN_ID = 5423849679

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

ACTIVE_QUIZ_TRACKER = {}
POLL_CORRECT_MAP = {}
READY_MATCHES = {}
ADMIN_POST_STORAGE = {}
PENDING_QUIZZES = {}
USER_CUSTOM_BUILDERS = {}

BANNER_IMAGES = {
    "talaba": "https://images.unsplash.com/photo-1457369804613-52c61a468e7d?w=900&auto=format&fit=crop&q=80",
    "oqituvchi": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=900&auto=format&fit=crop&q=80",
    "abituriyent": "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=900&auto=format&fit=crop&q=80",
    "izlanuvchi": "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=900&auto=format&fit=crop&q=80"
}

IMZO = (
    "\n\n╭───────────────────────╮\n"
    f"  🏛 **Rasmiy kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})\n"
    "  ✨ **AI Asistent:** @aitilshunosbot\n"
    "╰───────────────────────╯"
)

CERT_ESSAY_TOPICS = [
    "Aksariyat maktab bitiruvchilari oliy ta'limni talab etmaydigan zamonaviy kasblarni egallashga qiziqish bildirishsa, ayrimlar zamonaviy kasblar insonga butun umrlik faoliyat bo'lib qolishiga ishonishmaydi.",
    "Ba'zilar bolaga mukammal bilim berish uchun uni xususiy maktabda o'qitish kerak deb hisoblashsa, ayrimlar davlat maktabida ham mukammal bilim olish mumkin deb bilishadi.",
    "Ayrimlar turli shoular va yutuqli oʻyinlar odamlarning bir-biriga bo'lgan ishonchini soʻndiradi degan fikrda, ba'zilar esa bunday ko'ngilochar oʻyinlarning afzalliklari haqida gapirishadi.",
    "Ayrimlar chet tilini o'rganish madaniylikning bir belgisi deb bilsalar, ba'zilar o'zga tilini bilish moddiy hayotni ta'minlaydi deydilar.",
    "Hozirgi kunda ayrim insonlar reklamalarga ma'lumot ulashishning eng samarali usuli deb qarasa, ayrimlar bu borada cheklovlar qo'yish kerak deb bilishadi.",
    "Ayrimlar ko'p farzandlilik davlat va jamiyat taraqqiyoti uchun foyda keltiradi deb bilsa, ayrimlar oilada farzand tarbiyasiga e'tibor yetarli bo'lmaydi deb hisoblashadi.",
    "Ko'p qavatli uylar qurilishining avj olishi shahar arxitekturasi va dizayniga yangicha tus beradi, biroq koʻp aholi bunday uylar o'rniga xonadon yoki manzarali yer maydoni qurilishini ma'qul topadi.",
    "Ba'zilar kredit yillar davomida ushalmagan orzularni amalga oshirishning qulay yo'li deb hisoblashadi, ayrimlari esa kredit ortiqcha xarajati va moliyaviy holatni qiyinlashtiradi degan fikrda.",
    "Bugungi kunda sodir bo'layotgan jinoyatlar OAV, internet tarmoqlari orqali ommaga taqdim etilmoqda. Oshkora ko'rsatilishi kimlar uchundir jinoyatga yo'l ochib berishi mumkin deb qaralsa, baʼzilar oshkor ko'rsatish tarafdori.",
    "Ayrimlar oilaviy muammolar aks etgan videolavhalarning ijtimoiy tarmoqlarda tarqalishi jamiyat ma'naviyatiga va ruhiyatiga salbiy ta'sir koʻrsatadi deb bilishsa, ayrimlar aksincha fikrda.",
    "Ayrimlar yaxshi yashash uchun bitta kasbning mohir ustasi bo'lish kerak deb bilishsa, ba'zilar bir necha kasbning egasi bo'lish foydaliroq deb hisoblashadi.",
    "Sun'iy intellektning insoniyat hayotiga ijobiy va salbiy ta'sirlari.",
    "Plastik qadoqdagi suv yoki vodoprovod suvi iste'moli: afzallik va kamchiliklar.",
    "O'qitishda milliy usullarni yanada rivojlantirish muhimmi yoki chet el tajribasini qo'llashmi?",
    "Anʼanaviy to'ylar xorijiy to'ylar kabi ixcham va zamonaviy tarzda o'tkazilishiga munosabat.",
    "Zamonaviy kitobxonlar audio kitoblarning afzalligini ta'kidlashmoqda, ammo ba'zilar bu fikrga qarshi.",
    "Psixologlar tarbiyada erkinlik muhimligini taʼkidlashmoqda, ammo ba'zilar erkinlik salbiy oqibatlarga olib keladi degan fikrda.",
    "Ba'zilar inson faoliyati tufayli yer shari zararlanib borayotganini ta'kidlashmoqda, ayrimlar esa uni yashash uchun yaxshiroq joyga aylantiradi deb o'ylaydi.",
    "Ba'zilar ta'lim jarayonida mehnat faoliyati bilan shug'ullansa tajriba oshadi deyishsa, ayrimlar faqat bilim olish muhimligini ta'kidlashadi."
]

def get_next_quiz_number(quiz_type):
    counters = load_data(COUNTERS_FILE)
    current = counters.get(quiz_type, 0) + 1
    counters[quiz_type] = current
    save_data(COUNTERS_FILE, counters)
    return current

def update_user_streak(user):
    conn = get_db_connection()
    cursor = conn.cursor()
    u_id = user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    row = cursor.execute("SELECT * FROM users WHERE user_id = ?", (u_id,)).fetchone()
    
    if row:
        streak = row["streak"]
        points = row["points"]
        last_active = row["last_active"]
        streak_broken = False
        
        if last_active == today_str:
            pass
        elif last_active == yesterday_str:
            streak += 1
            points += 25
        else:
            if last_active != "":
                streak_broken = True
            streak = 1
            points += 10
            
        cursor.execute("""
            UPDATE users 
            SET username = ?, first_name = ?, points = ?, streak = ?, last_active = ?, status = 'active'
            WHERE user_id = ?
        """, (user.username or "", user.first_name or "", points, streak, today_str, u_id))
    else:
        streak = 1
        points = 10
        streak_broken = False
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, points, streak, last_active, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
        """, (u_id, user.username or "", user.first_name or "", points, streak, today_str))
        
    conn.commit()
    conn.close()
    return streak, points, streak_broken

THEME_CATALOG = {
    "cat_fonetika": {
        "title": "🗣 Fonetika, orfoepiya va imlo qoidalari",
        "prompt": "Fonetika: unli va undoshlar tasnifi, tovush o'zgarishlari, bo'g'in, urg'u hamda rasmiy imlo mezonlari"
    },
    "cat_leksika": {
        "title": "📖 Leksikologiya, frazeologiya va paronimlar",
        "prompt": "Leksikologiya: o'z va o'zlashgan qatlam, ma'nodosh, shakldosh, zid ma'noli so'zlar, paronimlar lug'ati va frazeologik iboralar tahlili"
    },
    "cat_morf_mustaqil": {
        "title": "🧩 Morfologiya: Mustaqil so'z turkumlari",
        "prompt": "Mustaqil so'z turkumlari: ot, sifat, son, olmosh, ravish hamda fe'l nisbatlari, vazifa shakllari"
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
        "prompt": "Mumtoz adabiyot: Alisher Navoiy va Bobur ijodi, aruz vazni bahr va ruknlari, mumtoz she'riy janrlar hamda badiiy san'atlar"
    },
    "cat_jadid": {
        "title": "💡 Jadid va XX asr o'zbek adabiyoti",
        "prompt": "Jadid va XX asr adabiyoti: Behbudiy, Avloniy, Fitrat, Cho'lpon, Qodiriy, Oybek, G'afur G'ulom asarlari va qahramonlari tahlili"
    }
}

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
        "sources": "Boborahim Mashrab, Turdi Forog'iy, Muhammadrizo Ogahiy, Munis Xorazmiy yoki Nodirabegim asarlari"
    },
    {
        "epoch": "XX asr boshi Jadid ma'rifatparvarlik harakati davri",
        "sources": "Mahmudxo'ja Behbudiy maqolalari, Abdulla Avloniy ('Turkiy Guliston yoxud axloq'), Munavvarqori Abdurashidxonov, Abdurauf Fitrat yoki Abdulhamid Cho'lpon publitsistikasi"
    },
    {
        "epoch": "XX asr o'zbek adabiyoti durdonalari va ma'rifiy merosi",
        "sources": "Abdulla Qodiriy ('O'tkan kunlar', 'Mehrobdan chayon'), Oybek, G'afur G'ulom, Erkin Vohidov, Abdulla Oripov yoki O'tkir Hoshimov"
    }
]

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

def get_main_menu(user_id=None):
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(
        tele_types.KeyboardButton("🎓 Talabalar uchun"),
        tele_types.KeyboardButton("👨‍🏫 O'qituvchilar uchun")
    )
    markup.row(
        tele_types.KeyboardButton("🎒 Abituriyentlar uchun"),
        tele_types.KeyboardButton("🛠 Quiz Test Tuzuvchi")
    )
    markup.row(
        tele_types.KeyboardButton("🔬 Ilmiy izlanuvchilar uchun"),
        tele_types.KeyboardButton("👤 Shaxsiy kabinet")
    )
    markup.row(
        tele_types.KeyboardButton("🏆 Jonli Reyting Doskasi")
    )
    if user_id and int(user_id) == int(ADMIN_ID):
        markup.row(
            tele_types.KeyboardButton("☀️ Kun hikmati (Admin)"),
            tele_types.KeyboardButton("⚡️ Motivatsiya (Admin)")
        )
        markup.row(tele_types.KeyboardButton("📊 Boshqaruv & Statistika"))
    return markup

def send_section_card(chat_id, group_name):
    if group_name == "talaba":
        img = BANNER_IMAGES["talaba"]
        caption = (
            "╭──── 🎓 **TALABALAR VA FILOLOGLAR KABINETI** ────╮\n\n"
            "▫️ Mumtoz g'azaliyot badiiyati va poetik san'atlar\n"
            "▫️ Aruz tizimi: hijolar vazni, bahrlar va taf'ilalar\n"
            "▫️ Eski turkiy til manbalari hamda nodir leksik qatlam\n"
            "▫️ Rahmatullayev etimologik lug'ati asosidagi tahlillar\n\n"
            "👇 *Kerakli tahlil turini tanlang:* \n"
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
            "▫️ **Milliy sertifikat esselari:** Tekshiruv, 19+ mavzular banki, namunalar\n"
            "▫️ O'TIL izohli lug'ati, rasmiy imlo va orfoepiya qoidalari\n"
            "▫️ **BMB 30 talik Test:** Davlat imtihoni standarti (30 soniya)\n"
            "▫️ **Mavzuli BMB Test:** 5-11-sinf darsliklari katalogi va erkin mavzu\n\n"
            "👇 *Kerakli tayyorgarlik bo'limini tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="🎯 Milliy sertifikat esselari", callback_data="hub_milliy_sertifikat"),
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

def send_cert_essay_hub(chat_id):
    caption = (
        "╭── 🎯 **MILLIY SERTIFIKAT ESSELARI MARKAZI** ──╮\n\n"
        "Ona tili va adabiyot fanidan Milliy sertifikat 50 ballik esse talablari "
        "va baholash mezonlari asosidagi maxsus bo'lim:\n\n"
        "▫️ **Esse tekshiruvi (50 ballik):** Yozgan matningizni mezonlar bo'yicha ekspert tahlil qildiring;\n"
        "▫️ **Esse mavzulari:** 19 ta rasmiy mavzular banki va yangi AI mavzular tavsiyasi;\n"
        "▫️ **Namunaviy esselar:** 20 ta tayyor namunalar kutubxonasi va AI generatsiyasi.\n\n"
        "👇 *Kerakli xizmatni tanlang:* \n"
        "╰──────────────────────────────────────────────╯"
    )
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(text="✍️ Esse tekshiruvi (50 ballik mezon)", callback_data="btn_esse"),
        tele_types.InlineKeyboardButton(text="💡 Esse mavzulari (Bank & AI)", callback_data="cert_topics_hub"),
        tele_types.InlineKeyboardButton(text="📚 Namunaviy esselar (20 ta namuna & AI)", callback_data="cert_samples_hub_0"),
        tele_types.InlineKeyboardButton(text="🔙 Abituriyent bo'limiga qaytish", callback_data="back_to_abituriyent")
    )
    bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)

def send_cert_topics_hub(chat_id):
    caption = (
        "╭── 💡 **MILLIY SERTIFIKAT ESSE MAVZULARI** ──╮\n\n"
        "Quyida Milliy sertifikat imtihonlarida tushadigan asosiy yo'nalishlar bo'yicha tayyor mavzular banki keltirilgan:\n\n"
        "👇 *Tanlang:* \n"
        "╰────────────────────────────────────────────╯"
    )
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(text="📋 19 ta tayyor mavzular banki", callback_data="view_all_cert_topics"),
        tele_types.InlineKeyboardButton(text="✨ Yangi ishonchli mavzular taklifi (AI)", callback_data="generate_new_topics"),
        tele_types.InlineKeyboardButton(text="🔙 Milliy sertifikat markaziga qaytish", callback_data="hub_milliy_sertifikat")
    )
    bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)

def show_all_cert_topics(chat_id):
    text = "╭── 📋 **19 TA RASMIY ESSE MAVZULARI BANKI** ──╮\n\n"
    for idx, top in enumerate(CERT_ESSAY_TOPICS, 1):
        text += f"**{idx}.** {top}\n\n"
    text += "╰──────────────────────────────────────────╯"
    
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(text="✨ AI orqali yangi mavzu topish", callback_data="generate_new_topics"),
        tele_types.InlineKeyboardButton(text="🔙 Mavzular bo'limiga qaytish", callback_data="cert_topics_hub")
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

def send_cert_samples_page(chat_id, message_id=None, page=0):
    per_page = 5
    total = len(SAMPLE_ESSAYS)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = page * per_page
    end = min(start + per_page, total)

    text = (
        f"╭── 📚 **NAMUNAVIY ESSELAR KUTUBXONASI** ──╮\n\n"
        f"Ushbu bo'limda Milliy sertifikat mezonlariga to'liq mos namunalar mavjud.\n"
        f"📄 *Sahifa: {page + 1}/{total_pages} (Jami {total} ta namuna)*\n\n"
        "O'qimoqchi bo'lgan essengizni tanlang:\n"
        "╰──────────────────────────────────────────╯"
    )

    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    for essay in SAMPLE_ESSAYS[start:end]:
        markup.add(tele_types.InlineKeyboardButton(text=f"📖 {essay['id']}. {essay['title']}", callback_data=f"read_essay_{essay['id']}"))

    nav_row = []
    if page > 0:
        nav_row.append(tele_types.InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"cert_samples_hub_{page - 1}"))
    if page + 1 < total_pages:
        nav_row.append(tele_types.InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"cert_samples_hub_{page + 1}"))
    if nav_row:
        markup.row(*nav_row)

    markup.add(
        tele_types.InlineKeyboardButton(text="✍️ Yangi mavzuda AI Namunaviy Esse tuzish", callback_data="ai_write_sample_essay"),
        tele_types.InlineKeyboardButton(text="🔙 Milliy sertifikat markaziga qaytish", callback_data="hub_milliy_sertifikat")
    )

    if message_id:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

def show_user_profile(chat_id, user):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user.id,)).fetchone()
    conn.close()

    results = load_data(RESULTS_FILE)
    u_id = str(user.id)
    
    points = row["points"] if row else 0
    streak = row["streak"] if row else 1
    
    test_data = results.get(u_id, {})
    best_correct = test_data.get("correct", 0)
    
    sorted_res = sorted(results.items(), key=lambda x: -x[1].get("correct", 0))
    rank = "Ishtirok etmagan"
    for idx, (uid_k, _) in enumerate(sorted_res, 1):
        if uid_k == u_id:
            rank = f"#{idx}-o'rin"
            break

    profile_text = (
        "╭──── 👤 **SIZNING SHAXSIY KABINETINGIZ** ────╮\n\n"
        f"▫️ **Ism-familiya:** {user.first_name}\n"
        f"▫️ **Telegram ID:** `{user.id}`\n\n"
        f"🔥 **Olovli seriya (Streak):** `{streak} kun uzluksiz`\n"
        f"🎖 **To'plangan ballar (XP):** `{points} ball`\n"
        f"📊 **BMB testdagi eng yaxshi natija:** `{best_correct}/30 to'g'ri`\n"
        f"🏆 **Respublika reytingidagi o'rningiz:** `{rank}`\n\n"
        "💡 *Eslatma: Har kuni botga kirib test ishlash orqali olovli seriyangizni saqlab qoling!*\n"
        "╰─────────────────────────────────────────────╯"
    )
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(
            text="🏆 Jonli Reyting Doskasi (Mini-App)", 
            web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
        )
    )
    bot.send_message(chat_id, profile_text, parse_mode="Markdown", reply_markup=markup)

def send_themed_test_hub(chat_id):
    caption = (
        "╭── 📚 **MAVZULASHTIRILGAN BMB TEST MARKAZI** ──╮\n\n"
        "Ona tili va adabiyoti fanidan 30 talik test topshirish uchun "
        "o'zingizga qulay usulni tanlang:\n\n"
        "1️⃣ **Mavzular katalogidan tanlash** — 5-11-sinf darsliklarining asosiy bo'limlari;\n"
        "2️⃣ **Mavzuni o'zingiz kiritish** — aniq dars yoki tor yo'nalish nomini yozasiz.\n\n"
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
        "Quyidagi ro'yxatdan tanlang:\n\n"
        "╰──────────────────────────────────────────────╯"
    )
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    for cat_key, cat_data in THEME_CATALOG.items():
        markup.add(tele_types.InlineKeyboardButton(text=cat_data["title"], callback_data=f"seltheme_{cat_key}"))
    markup.add(tele_types.InlineKeyboardButton(text="🔙 Orqaga", callback_data="btn_bmb_themed_hub"))
    bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)

def send_quiz_creator_hub(chat_id):
    caption = (
        "╭── 🛠 **QUIZ TEST TUZUVCHI KONSTRUKTORI** ──╮\n\n"
        "Siz ushbu bo'limda o'zingiz xohlagan mavzu yoki matn asosida "
        "100% xatosiz, 4 variantli professional Quiz test paketini tuzishingiz mumkin!\n\n"
        "✨ **Imkoniyatlar:**\n"
        "▫️ Erkin mavzu yoki darslik parchasini kiritish;\n"
        "▫️ Savollar sonini (5, 10, 15, 20 yoki 30 ta) tanlash;\n"
        "▫️ Savolga ajratilgan vaqtni (15, 30 yoki 45 soniya) belgilash;\n"
        "▫️ Testni o'z guruhingizga tashlab, **jonli bellashuv** o'tkazish!\n\n"
        "👇 *Test tuzishni boshlash uchun bosing:* \n"
        "╰──────────────────────────────────────────╯"
    )
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(text="🚀 Yangi Quiz Test tuzish", callback_data="start_custom_quiz_builder")
    )
    bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=markup)

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
            text="🔍 *DTS, OAK va Milliy sertifikat mezonlari bo'yicha qoliplashmoqda...*",
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
        f"🏛 **Rasmiy kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})"
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
            url=CHANNEL_URL
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
        f"👉 **Kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})\n\n"
        "Obuna bo'lgach, quyidagi tugma orqali tasdiqlang.\n"
        "╰─────────────────────────────────────╯"
    )
    bot.send_message(chat_id, matn, parse_mode="Markdown", reply_markup=markup)

SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi Fanlar akademiyasi Til va adabiyot instituti yetakchi filologi, "
    "OAK eksperti hamda BMB (DTM) va Milliy sertifikat bo'yicha bosh ilmiy-metodistsiz.\n\n"
    "QAT'IY TALABLAR (QUIZ TESTLAR BO'YICHA):\n"
    "1. Test savollari, variantlar va izohlar 100% XATOSIZ, akademik aniqlikda, hozirgi rasmiy imlo va orfoepiya qoidalariga "
    "qat'iy rioya etgan holda tuzilsin. Hech qanday imloviy, grammatik, mantiqiy yoki uslubiy noaniqlikka yo'l qo'yilmasin.\n"
    "2. Har bir savol uchun taqdim etilgan 4 ta variant mutlaqo mustaqil, bir-birini takrorlamaydigan va haqiqiy bo'lsin. "
    "'correct_option_id' aynan to'g'ri variantning 0 dan 3 gacha bo'lgan to'g'ri indeksini ifodalashi shart.\n"
    "3. Adabiyotga oid savollarda muallif, asar nomi, qahramonlar va tarixiy faktlar faqat amaldagi 5-11-sinf darsliklariga to'liq mos bo'lsin.\n\n"
    "QAT'IY TAQIQLAR:\n"
    "1. Diniy aqidaviy bahslar, amallar va fatvolar mutlaqo taqiqlanadi.\n"
    "2. Amaldagi davlat boshqaruvi, siyosat va amaldorlar shaxsi haqida ma'lumot berilmaydi.\n"
    "3. Tibbiy va huquqiy maslahatlar berilmaydi.\n"
    "4. Buzg'unchilik, ekstremizm va haqoratli mazmun 100% rad etiladi."
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
                        temperature=0.3
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
                        temperature=0.4
                    )
                )
                raw = response.text.strip()
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                questions = json.loads(raw)
                if isinstance(questions, list) and len(questions) >= 5:
                    cleaned_questions = []
                    for q in questions:
                        opts = [str(o).strip() for o in q.get("options", []) if str(o).strip()]
                        if len(opts) == 4 and 0 <= int(q.get("correct_option_id", 0)) < 4:
                            cleaned_questions.append(q)
                    if len(cleaned_questions) >= min(5, count):
                        return cleaned_questions[:count]
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

def get_themed_bmb_questions(theme_name, count=30):
    local_base = load_local_knowledge_base()
    if local_base and "tests" in local_base and len(local_base["tests"]) > 0:
        base_tests = local_base["tests"]

        if any(k in theme_name.lower() for k in ["barcha", "umumiy", "dtm", "bmb"]):
            return random.sample(base_tests, min(len(base_tests), count))

        filtered = [
            t for t in base_tests 
            if theme_name.lower() in t.get("bolim", "").lower()
        ]
        if len(filtered) >= count:
            return random.sample(filtered, count)

    seed = random.randint(10000, 99999)
    prompt = (
        f"O'zbekiston Respublikasi BMB (DTM) va Milliy sertifikat standarti bo'yicha "
        f"amaldagi 5-11-sinf Ona tili va adabiyot darsliklari asosida aynan '{theme_name}' mavzusida "
        f"TO'LIQ {count} TA 100% XATOSIZ, ORIGINAL, ILMIY VA USLUBIY JIHATDAN MUKAMMAL Quiz test tuzing (Seed #{seed}).\n\n"
        "QAT'IY QOIDALAR:\n"
        "1. Darslik faktlariga 100% mos bo'lsin. Imloviy va grammatik xatolarga mutlaqo yo'l qo'yilmasin.\n"
        "2. Har bir savolda aniq 4 ta variant (A, B, C, D) bo'lsin, birortasi takrorlanmasin.\n"
        "3. correct_option_id (0, 1, 2 yoki 3) aynan to'g'ri javobga to'liq muvofiq kelsin.\n"
        "Faqat quyidagi JSON formatida qaytaring:\n"
        "[\n"
        "  {\n"
        '    "question": "Savol matni (maks 250 belgi)",\n'
        '    "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '    "correct_option_id": 0,\n'
        '    "explanation": "Qisqa ilmiy izoh va darslik manbasi (maks 180 belgi)"\n'
        "  }\n"
        "]\n"
        f"DIQQAT: Ro'yxatda aniq {count} ta savol bo'lsin. Variantlar uzunligi 95 belgidan oshmasin."
    )
    return generate_quiz_batch(prompt, count)

def get_attestation_questions():
    seed = random.randint(10000, 99999)
    prompt = (
        "Maktabgacha va maktab ta'limi vazirligi pedagoglar attestatsiyasi rasmiy spetsifikatsiyasi asosida "
        f"Ona tili va adabiyot fani o'qituvchilari uchun TO'LIQ 40 TA 100% XATOSIZ, MUKAMMAL test tuzing (Seed #{seed}).\n\n"
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

@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    poll_id = poll_answer.poll_id
    poll_info = POLL_CORRECT_MAP.get(poll_id)
    if not poll_info:
        return

    chat_id = poll_info["chat_id"]
    correct_opt = poll_info["correct_option_id"]
    q_start_time = poll_info.get("sent_time", time.time())
    
    if not poll_answer.option_ids:
        return
    chosen_opt = poll_answer.option_ids[0]

    user = poll_answer.user
    u_id = user.id
    u_name = user.first_name or "Ishtirokchi"
    if user.last_name:
        u_name += f" {user.last_name}"

    # Savolga javob berish uchun sarflangan vaqt (soniya)
    time_spent_on_q = max(0.1, time.time() - q_start_time)

    if chat_id in ACTIVE_QUIZ_TRACKER:
        scores = ACTIVE_QUIZ_TRACKER[chat_id]["scores"]
        if u_id not in scores:
            scores[u_id] = {
                "name": u_name,
                "correct": 0,
                "total_answered": 0,
                "total_time": 0.0
            }
        
        scores[u_id]["total_answered"] += 1
        scores[u_id]["total_time"] += time_spent_on_q
        
        if chosen_opt == correct_opt:
            scores[u_id]["correct"] += 1

def run_interactive_quiz_loop(target_chat_id, questions, duration_per_q, title):
    total_q = len(questions)
    is_anon = False  # Barcha ishtirokchilar kim nima belgilaganini jonli ko'rishi uchun

    start_time = time.time()
    ACTIVE_QUIZ_TRACKER[target_chat_id] = {
        "scores": {},
        "total_q": total_q
    }

    bot.send_message(
        target_chat_id,
        f"🏁 **DIQQAT, {title.upper()} BOSHLANDI!**\n\n"
        f"▫️ Jami savollar: `{total_q} ta`\n"
        f"▫️ Har bir savolga vaqt: `⏳ {duration_per_q} soniya`\n"
        f"▫️ Rejim: **Ochiq so'rovnoma (Kim qaysi javobni tanlagani ko'rinadi)**\n"
        f"▫️ Reyting mezoni: **To'g'ri javoblar soni va sarflangan umumiy vaqt**\n"
        f"▫️ Rasmiy kanal: [{CHANNEL_USERNAME}]({CHANNEL_URL})\n\n"
        "Har bir to'g'ri javob qayd etiladi va yakunda **REYTING JADVALI** e'lon qilinadi!",
        parse_mode="Markdown",
        disable_web_page_preview=True
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

        explanation = f"{q_data.get('explanation', '')}\n👉 @onatilidanyordam"[:195]

        try:
            poll_sent_at = time.time()
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
                "correct_option_id": correct_id,
                "sent_time": poll_sent_at
            }
        except Exception as err:
            try:
                poll_sent_at = time.time()
                poll_msg = bot.send_poll(
                    chat_id=target_chat_id,
                    question=question_text,
                    options=options,
                    type="quiz",
                    correct_option_id=correct_id,
                    explanation=explanation,
                    is_anonymous=True,
                    open_period=duration_per_q
                )
                POLL_CORRECT_MAP[poll_msg.poll.id] = {
                    "chat_id": target_chat_id,
                    "correct_option_id": correct_id,
                    "sent_time": poll_sent_at
                }
            except Exception:
                pass

        time.sleep(duration_per_q + 2)

    tracker = ACTIVE_QUIZ_TRACKER.pop(target_chat_id, None)
    scores = tracker["scores"] if tracker else {}

    results = load_data(RESULTS_FILE)

    if scores:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for uid, info in scores.items():
            results[str(uid)] = {
                "name": info["name"],
                "correct": info["correct"],
                "duration": round(info["total_time"], 1),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            cursor.execute("""
                UPDATE users SET points = points + ? WHERE user_id = ?
            """, (info["correct"] * 2, uid))
            
        conn.commit()
        conn.close()
        save_data(RESULTS_FILE, results)

        # SARALASH MEZONI:
        # 1. To'g'ri javoblar ko'pligi (kamayish tartibida: -x[1]["correct"])
        # 2. Sarflangan umumiy vaqt kamligi (o'sish tartibida: x[1]["total_time"])
        sorted_participants = sorted(
            scores.items(),
            key=lambda x: (-x[1]["correct"], x[1]["total_time"])
        )

        leaderboard_text = ""
        for rank, (uid, info) in enumerate(sorted_participants, 1):
            if rank == 1:
                medal = "🥇"
            elif rank == 2:
                medal = "🥈"
            elif rank == 3:
                medal = "🥉"
            else:
                medal = f"**{rank}.**"
                
            perc = round((info["correct"] / total_q) * 100, 1)
            spent_time = round(info["total_time"], 1)
            leaderboard_text += (
                f"{medal} **{info['name']}** — `{info['correct']}/{total_q}` to'g'ri "
                f"(`{perc}%`) • ⏱ `{spent_time}s`\n"
            )

        finish_msg = (
            f"╔════════════════════════════════╗\n"
            f"  🏆 **{title.upper()} JONLI REYTINGI**\n"
            f"╚════════════════════════════════╝\n\n"
            f"👥 Ishtirokchilar: `{len(sorted_participants)} nafar`\n"
            f"📊 Jami savollar: `{total_q} ta`\n\n"
            "🏅 **G'OLIBLAR VA NATIJALAR (Ball & Vaqt bo'yicha):**\n"
            f"{leaderboard_text}\n"
            "────────────────────────────────\n"
            f"✨ Rasmiy filologik kanalimiz: [{CHANNEL_USERNAME}]({CHANNEL_URL})"
        )
    else:
        finish_msg = (
            f"╔════════════════════════════════╗\n"
            f"  🏆 **{title.upper()} YAKUNLANDI!**\n"
            f"╚════════════════════════════════╝\n\n"
            "Test yakunlandi. Hech bir ishtirokchi javob belgilamadi.\n\n"
            f"Rasmiy kanal: [{CHANNEL_USERNAME}]({CHANNEL_URL})"
        )

    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(
            text="🏆 Jonli Reyting Doskasi (Mini-App)", 
            web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
        ),
        tele_types.InlineKeyboardButton(text="📤 Ushbu testni guruhga ulashish", switch_inline_query="test_taklifi"),
        tele_types.InlineKeyboardButton(text="📢 Rasmiy kanalga a'zo bo'lish", url=CHANNEL_URL)
    )
    bot.send_message(target_chat_id, finish_msg, parse_mode="Markdown", reply_markup=markup, disable_web_page_preview=True)

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
        tele_types.InlineKeyboardButton(text="📢 Rasmiy kanalga a'zo bo'lish", url=CHANNEL_URL)
    )

    announcement = (
        f"╔════════════════════════════════╗\n"
        f"  🧠 **{title.upper()}**\n"
        f"╚════════════════════════════════╝\n\n"
        f"▫️ Savollar soni: `{len(questions)} ta`\n"
        f"▫️ Har bir savolga: `⏳ {duration_per_q} soniya`\n"
        f"▫️ Rejim: **Ochiq test (Har kimning javobi ko'rinadi)**\n"
        f"▫️ Rasmiy kanal: [{CHANNEL_USERNAME}]({CHANNEL_URL})\n\n"
        "⚠️ **Qoida:** Bellashuv start olishi uchun kamida **3 nafar ishtirokchi** "
        "«Men tayyorman» tugmasini bosishi lozim!"
    )
    bot.send_message(chat_id, announcement, parse_mode="Markdown", reply_markup=markup, disable_web_page_preview=True)

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
            tele_types.InlineKeyboardButton(text="📢 Rasmiy kanalga a'zo bo'lish", url=CHANNEL_URL)
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
                text=f"🎉 **Yetarli ishtirokchilar yig'ildi! (Tayyorlar: {names})**\n\n🚀 Bellashuv 5 soniyadan so'ng start oladi...",
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
            tele_types.InlineKeyboardButton(text="📢 Rasmiy kanalga e'lon qilish (@onatilidanyordam)", callback_data=f"act_chan_{quiz_id}"),
            tele_types.InlineKeyboardButton(text="👥 Guruhga tashlash (Bot admin bo'lgan)", callback_data=f"act_sendgrp_{quiz_id}"),
            tele_types.InlineKeyboardButton(text="📤 Istalgan guruhga ulashish (Inline)", switch_inline_query=quiz_id),
            tele_types.InlineKeyboardButton(text="🤖 Botning o'zida yakkaxon ishlash (Darhol)", callback_data=f"act_bot_{quiz_id}")
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
            tele_types.InlineKeyboardButton(text="👥 Guruhga tashlash (Bot admin bo'lgan)", callback_data=f"act_sendgrp_{quiz_id}"),
            tele_types.InlineKeyboardButton(text="📤 Istalgan guruhga ulashish (Inline)", switch_inline_query=quiz_id)
        )
        bot.send_message(
            chat_id,
            f"🎉 **{title}** 100% xatosiz va mukammal tayyorlandi!\nQayerda test ishlamoqchisiz? Tanlang:",
            parse_mode="Markdown",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith(("act_chan_", "act_bot_", "act_sendgrp_")))
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
            text=f"✅ **{q_data['title']}** rasmiy {CHANNEL_USERNAME} kanaliga e'lon qilindi!\n3 kishi «Tayyorman»ni bosgach ochiq test boshlanadi."
        )

    elif data.startswith("act_bot_"):
        quiz_id = data.replace("act_bot_", "")
        q_data = PENDING_QUIZZES.get(quiz_id)
        if not q_data:
            bot.answer_callback_query(call.id, "Test ma'lumoti eskirgan.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Test darhol boshlanmoqda!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        threading.Thread(
            target=run_interactive_quiz_loop,
            args=(call.message.chat.id, q_data["questions"], q_data["duration"], q_data["title"]),
            daemon=True
        ).start()

    elif data.startswith("act_sendgrp_"):
        quiz_id = data.replace("act_sendgrp_", "")
        q_data = PENDING_QUIZZES.get(quiz_id)
        if not q_data:
            bot.answer_callback_query(call.id, "Test ma'lumoti eskirgan.", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "👥 **TESTNI GURUHGA YUBORISH:**\n\n"
            "1. Botni guruhingizga qo'shib, unga **Admin** huquqini bering.\n"
            "2. Guruhingizning **Usernamesini** (masalan, `@mening_guruhim`) yoki **ID raqamini** (masalan, `-100123456789`) yozib yuboring:\n\n"
            "*(Bekor qilish uchun `/cancel` deb yozing)*",
            parse_mode="Markdown"
        )
        def forward_quiz_to_group(m):
            target_chat = m.text.strip()
            if target_chat == "/cancel":
                bot.send_message(call.message.chat.id, "❌ Guruhga yuborish bekor qilindi.")
                return
            try:
                setup_match_lobby(target_chat, q_data["questions"], q_data["duration"], q_data["title"])
                bot.send_message(
                    call.message.chat.id, 
                    f"✅ **{q_data['title']}** muvaffaqiyatli `{target_chat}` guruhiga e'lon qilindi!\n"
                    "Guruhda 3 kishi «Tayyorman»ni bosishi bilan ochiq test start oladi va barchaning natijasi ko'rinadi."
                )
            except Exception as ex:
                bot.send_message(
                    call.message.chat.id,
                    f"❌ Guruhga yuborib bo'lmadi!\nSabab: Bot mazkur guruhda admin emas yoki guruh ID/username xato kiritildi.\n\n*Texnik xato: {ex}*",
                    parse_mode="Markdown"
                )
        bot.register_next_step_handler(msg, forward_quiz_to_group)

@bot.callback_query_handler(func=lambda call: call.data == "start_custom_quiz_builder")
def callback_start_quiz_builder(call):
    uid = call.from_user.id
    USER_CUSTOM_BUILDERS[uid] = {}
    bot.answer_callback_query(call.id)
    
    msg = bot.send_message(
        call.message.chat.id,
        "✍️ **1-QADAM: Test mavzusini yoki matnni kiriting:**\n\n"
        "Qaysi mavzuda yoki qaysi matn asosida Quiz test tuzmoqchisiz? Yozib yuboring:\n"
        "👉 *Masalan: «Boburnoma fitonimlari va etnolingvistikasi», «Eski turkiy til leksikasi», «Qo'shma gap sintaksisi» yoki darslikdan parcha.*",
        parse_mode="Markdown"
    )
    def step_get_topic(m):
        topic = m.text.strip()
        USER_CUSTOM_BUILDERS[uid]["topic"] = topic
        
        markup = tele_types.InlineKeyboardMarkup(row_width=3)
        markup.row(
            tele_types.InlineKeyboardButton(text="5 ta savol", callback_data="cb_qcount_5"),
            tele_types.InlineKeyboardButton(text="10 ta savol", callback_data="cb_qcount_10"),
            tele_types.InlineKeyboardButton(text="15 ta savol", callback_data="cb_qcount_15")
        )
        markup.row(
            tele_types.InlineKeyboardButton(text="20 ta savol", callback_data="cb_qcount_20"),
            tele_types.InlineKeyboardButton(text="30 ta savol", callback_data="cb_qcount_30")
        )
        bot.send_message(
            call.message.chat.id,
            f"📌 **Mavzu qabul qilindi:** *{topic[:80]}...*\n\n"
            "📊 **2-QADAM: Test nechta savoldan iborat bo'lsin?** Tanlang:",
            parse_mode="Markdown",
            reply_markup=markup
        )
    bot.register_next_step_handler(msg, step_get_topic)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cb_qcount_"))
def callback_quiz_builder_count(call):
    uid = call.from_user.id
    count = int(call.data.replace("cb_qcount_", ""))
    if uid not in USER_CUSTOM_BUILDERS:
        USER_CUSTOM_BUILDERS[uid] = {"topic": "Ona tili va adabiyot umumiy"}
    USER_CUSTOM_BUILDERS[uid]["count"] = count
    bot.answer_callback_query(call.id)

    markup = tele_types.InlineKeyboardMarkup(row_width=3)
    markup.row(
        tele_types.InlineKeyboardButton(text="⏳ 15 soniya", callback_data="cb_qtime_15"),
        tele_types.InlineKeyboardButton(text="⏳ 30 soniya", callback_data="cb_qtime_30"),
        tele_types.InlineKeyboardButton(text="⏳ 45 soniya", callback_data="cb_qtime_45")
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📊 Savollar soni: `{count} ta`\n\n⏱ **3-QADAM: Har bir savolga qancha vaqt berilsin?** Tanlang:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("cb_qtime_"))
def callback_quiz_builder_finish(call):
    uid = call.from_user.id
    duration = int(call.data.replace("cb_qtime_", ""))
    builder_data = USER_CUSTOM_BUILDERS.get(uid, {})
    topic = builder_data.get("topic", "Ona tili va adabiyot")
    count = builder_data.get("count", 10)
    
    bot.answer_callback_query(call.id, "Test generatsiyasi boshlandi...")
    status_msg = bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🧠 *AI Tilshunos ekspertimiz «{topic[:50]}» bo'yicha 100% xatosiz {count} ta test savolini shakllantirmoqda... Iltimos kuting!*",
        parse_mode="Markdown"
    )

    def generate_and_dispatch():
        try:
            questions = get_themed_bmb_questions(topic, count=count)
            quiz_title = f"«{topic[:40]}» testi ({count} ta)"
            try:
                bot.delete_message(call.message.chat.id, status_msg.message_id)
            except Exception:
                pass
            offer_quiz_dispatch(call.message.chat.id, uid, questions, duration_per_q=duration, title=quiz_title)
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Test shakllantirishda xatolik yuz berdi: {e}")

    threading.Thread(target=generate_and_dispatch, daemon=True).start()

@bot.message_handler(commands=['quiz_start'])
def cmd_quiz_start_group(message):
    chat_type = message.chat.type
    if chat_type in ['group', 'supergroup']:
        bot.reply_to(
            message, 
            "⏳ *Guruh uchun 100% xatosiz BMB 30 talik test shakllanmoqda... Iltimos kuting!*", 
            parse_mode="Markdown"
        )
        try:
            bmb_num = get_next_quiz_number("bmb_30")
            quiz_title = f"№{bmb_num} BMB 30 talik test (Guruh Bellashuvi)"
            questions = get_themed_bmb_questions("5-11-sinf barcha darsliklari", 30)
            setup_match_lobby(message.chat.id, questions, duration_per_q=30, title=quiz_title)
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")
    else:
        bot.reply_to(message, "Ushbu buyruq faqat Telegram guruhlarida ishlaydi.")

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
                bot.send_message(CHANNEL_USERNAME, content, parse_mode="Markdown", disable_web_page_preview=True)
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

def get_verified_didactic_content(content_type="hikmat"):
    chosen_epoch = random.choice(HISTORICAL_EPOCHS)
    seed = random.randint(1000, 99999)

    if content_type == "hikmat":
        prompt = (
            f"Siz o'zbek adabiyoti tarixi va manbashunoslik bo'yicha yuksak mutaxassissiz.\n"
            f"Aynan quyidagi adabiy-tarixiy davrga mansub durdona asarlardan 1 ta didaktik hikmatni keltiring:\n"
            f"🏛 **Davr:** {chosen_epoch['epoch']}\n"
            f"📜 **Tavsiya etiladigan manbalar:** {chosen_epoch['sources']}\n"
            f"Identifikator: #{seed}\n\n"
            "QAT'IY TALABLAR:\n"
            "1. Mazkur hikmat ilm, odob, qanoat, vaqt qadri, adolat yoki donolik xususida bo'lsin.\n"
            "2. Sun'iy ravishda to'qilmasin! Haqiqiy asarlardan aniq iqtibos oling.\n"
            "3. Diniy, siyosiy, tibbiy yoki huquqiy mavzulardan 100% chetlashing.\n\n"
            "Qat'iy format:\n"
            "🏛 **Davr:** [Tanlangan davr nomi]\n\n"
            "[HIKMAT MATNI]\n\n"
            "📚 Aniq manba: [Muallif, asar nomi, bob yoki bayt ko'rsatkichi]"
        )
    else:
        prompt = (
            f"Siz ma'rifiy meros va milliy taraqqiyot bo'yicha mutaxassis olimsiz.\n"
            f"Aynan quyidagi davr mutafakkirlari asarlaridan ilm olishga va shaxsiy rivojlanishga undovchi 1 ta motivatsion fikr keltiring:\n"
            f"🏛 **Davr:** {chosen_epoch['epoch']}\n"
            f"📜 **Tavsiya etiladigan manbalar:** {chosen_epoch['sources']}\n"
            f"Identifikator: #{seed}\n\n"
            "QAT'IY TALABLAR:\n"
            "1. Sun'iy to'qilmasin! Haqiqiy doston, roman yoki maqolalardan olinsin.\n"
            "2. Diniy, siyosiy, tibbiy yoki huquqiy mavzulardan mutlaqo chetlashing.\n\n"
            "Qat'iy format:\n"
            "🏛 **Davr:** [Tanlangan davr nomi]\n\n"
            "[MOTIVATSIYA MATNI]\n\n"
            "📚 Aniq manba: [Muallif, asar nomi, sahifa ko'rsatkichi]"
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
    channel_post = f"{clean_text}\n\n───────────────\n🌟 **Rasmiy kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})"

    try:
        bot.send_message(CHANNEL_USERNAME, channel_post, parse_mode="Markdown", disable_web_page_preview=True)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"{call.message.text}\n\n✅ **Kanalga manbasiz muvaffaqiyatli joylandi!**"
        )
        bot.answer_callback_query(call.id, "Kanalga joylandi!")
    except Exception as e:
        bot.answer_callback_query(call.id, f"Xatolik: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith((
    "btn_", "theme_", "seltheme_", "hub_milliy_sertifikat", "cert_topics_hub", 
    "view_all_cert_topics", "generate_new_topics", "cert_samples_hub_", 
    "read_essay_", "ai_write_sample_essay", "back_to_abituriyent"
)))
def callback_button_actions(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    data = call.data

    if data == "back_to_abituriyent":
        try:
            bot.delete_message(cid, call.message.message_id)
        except Exception:
            pass
        send_section_card(cid, "abituriyent")

    elif data == "hub_milliy_sertifikat":
        send_cert_essay_hub(cid)

    elif data == "cert_topics_hub":
        send_cert_topics_hub(cid)

    elif data == "view_all_cert_topics":
        show_all_cert_topics(cid)

    elif data == "generate_new_topics":
        p = (
            "O'zbekiston Respublikasi Ona tili va adabiyot fanidan Milliy sertifikat "
            "standarti asosida dolzarb va 100% ishonchli manbalarga tayanadigan 5 ta ORIGINAL ESSE MAVZUSINI tuzib bering. "
            "Har bir mavzuning ikkala qarama-qarshi nuqtayi nazari aniq ifodalansin."
        )
        dynamic_ai_delivery(cid, p, uid, "yangi_esse_mavzulari")

    elif data.startswith("cert_samples_hub_"):
        page = int(data.replace("cert_samples_hub_", ""))
        send_cert_samples_page(cid, message_id=call.message.message_id, page=page)

    elif data.startswith("read_essay_"):
        e_id = int(data.replace("read_essay_", ""))
        found = next((item for item in SAMPLE_ESSAYS if item["id"] == e_id), None)
        if found:
            text = (
                f"╭── 📝 **NAMUNAVIY ESSE #{found['id']}** ──╮\n\n"
                f"📌 **Mavzu:** *{found['topic']}*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{found['text']}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🏆 **Baholash:** 50/50 ballik Milliy sertifikat standarti\n"
                f"╰──────────────────────────────────╯"
            )
            markup = tele_types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                tele_types.InlineKeyboardButton(text="🔙 Namunalar ro'yxatiga qaytish", callback_data="cert_samples_hub_0"),
                tele_types.InlineKeyboardButton(text="🎯 Milliy sertifikat markaziga qaytish", callback_data="hub_milliy_sertifikat")
            )
            bot.send_message(cid, text, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "Esse topilmadi!", show_alert=True)

    elif data == "ai_write_sample_essay":
        msg = bot.send_message(
            cid, 
            "✍️ **Qaysi mavzuda 50 ballik namunaviy esse yozib beraylik?**\n\n"
            "Mavzuni to'liq yozib yuboring:", 
            parse_mode="Markdown"
        )
        def process_sample_writing(m):
            t_input = m.text.strip()
            p = (
                f"Ona tili va adabiyoti fanidan Milliy sertifikatning 50 ballik qat'iy mezonlari "
                f"asosida quyidagi mavzuda 100% ISHONCHLI, MUKAMMAL VA AKADEMIK NAMUNAVIY ESSE yozing:\n\n"
                f"Mavzu: '{t_input}'"
            )
            dynamic_ai_delivery(cid, p, uid, "namunaviy_esse")
        bot.register_next_step_handler(msg, process_sample_writing)

    elif data == "btn_esse":
        msg = bot.send_message(
            cid, 
            "📝 **Milliy sertifikat esse tekshiruvi (50 ballik):**\n\n"
            "Esse mavzusi va o'zingiz yozgan matnni to'liq yuboring. AI ekspert uni 5 ta mezon "
            "bo'yicha tekshirib, ball qo'yadi va xatolaringizni ko'rsatadi:", 
            parse_mode="Markdown"
        )
        p = "Ushbu esse matnini Milliy sertifikatning 50 ballik mezoni bo'yicha tekshiring: '{input}'"
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "esse"))

    elif data == "btn_bmb_themed_hub":
        send_themed_test_hub(cid)

    elif data == "theme_open_catalog":
        send_theme_catalog(cid)

    elif data == "theme_custom_input":
        msg = bot.send_message(
            cid, 
            "✍️ **Erkin mavzu bo'yicha test:**\n\n"
            "Qaysi darslik mavzusidan 30 talik test tuzmoqchisiz? Yozib yuboring:", 
            parse_mode="Markdown"
        )
        def start_custom_theme(m):
            theme = m.text.strip()
            quiz_title = f"«{theme}» mavzusi bo'yicha test (30 ta)"
            bot.send_message(cid, f"⏳ *«{theme}» bo'yicha 100% xatosiz test shakllanmoqda...*", parse_mode="Markdown")
            try:
                questions = get_themed_bmb_questions(theme, 30)
                offer_quiz_dispatch(cid, uid, questions, duration_per_q=30, title=quiz_title)
            except Exception as e:
                bot.send_message(cid, f"❌ Xatolik: {e}")
        bot.register_next_step_handler(msg, start_custom_theme)

    elif data.startswith("seltheme_"):
        cat_key = data.replace("seltheme_", "")
        cat_info = THEME_CATALOG.get(cat_key)
        if cat_info:
            quiz_title = f"{cat_info['title']} (30 ta)"
            bot.send_message(cid, f"⏳ *{cat_info['title']} bo'yicha 100% xatosiz test tayyorlanmoqda...*", parse_mode="Markdown")
            try:
                questions = get_themed_bmb_questions(cat_info["prompt"], 30)
                offer_quiz_dispatch(cid, uid, questions, duration_per_q=30, title=quiz_title)
            except Exception as e:
                bot.send_message(cid, f"❌ Xatolik: {e}")

    elif data == "btn_gazal":
        msg = bot.send_message(cid, "✍️ Badiiy tahlil qilmoqchi bo'lgan mumtoz baytingizni yuboring:")
        p = "Ushbu baytni badiiy tahlil qiling: '{input}'. San'atlari va so'zlar sharhini bering."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "gazal"))

    elif data == "btn_aruz":
        msg = bot.send_message(cid, "✍️ Aruzini aniqlamoqchi bo'lgan baytingizni yuboring:")
        p = "Ushbu baytni aruz tizimi bo'yicha tahlil qiling: '{input}'"
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

    elif data == "btn_izoh":
        msg = bot.send_message(cid, "📖 Izohini yoki imlosini bilmoqchi bo'lgan so'zingizni yozing:")
        p = "O'zbek tilining izohli lug'ati va imlo qoidalari asosida '{input}' so'zini to'liq sharhlang."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "izoh_imlo"))

    elif data == "btn_bmb_gen":
        bot.send_message(cid, "⏳ *BMB standarti bo'yicha 100% xatosiz 30 talik test shakllanmoqda...*", parse_mode="Markdown")
        try:
            bmb_num = get_next_quiz_number("bmb_30")
            quiz_title = f"№{bmb_num} BMB 30 talik test"
            questions = get_themed_bmb_questions("5-11-sinf barcha bo'limlari", 30)
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
        "esse": "Ushbu esse matnini Milliy sertifikat 50 ballik mezoni bo'yicha tekshiring: '{input}'",
        "namunaviy_esse": "Milliy sertifikat mezonlari asosida '{input}' mavzusida namunaviy esse yozing.",
        "maqola": "OAK talablari asosida '{input}' mavzusida maqola yozish uchun REJA va METODIK KO'RSATMA bering."
    }
    p = prompt_map.get(tag, "'{input}' bo'yicha ilmiy tahlil bering.")
    bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(call.message.chat.id, p.format(input=m.text), call.from_user.id, tag))

# --- INLINE QUERY HANDLER: GURUHLARGA ULASHISH TIZIMI ---
@bot.inline_handler(lambda query: True)
def handle_inline_quiz_share(inline_query):
    try:
        query_text = inline_query.query.strip()
        
        deep_link = f"https://t.me/aitilshunosbot?start={query_text}" if query_text else "https://t.me/aitilshunosbot"
        
        message_content = (
            "╔════════════════════════════════╗\n"
            "  🧠 **ONA TILI VA ADABIYOT TESTI**\n"
            "╚════════════════════════════════╝\n\n"
            "📚 Ushbu guruh a'zolari uchun maxsus test tavsiya etiladi!\n\n"
            "▫️ Mezon: **BMB va Milliy sertifikat standarti**\n"
            "▫️ Sifati: **100% xatosiz, akademik manbalar asosida**\n"
            "▫️ Imkoniyat: **Jonli reyting doskasi va olovli seriyalar**\n\n"
            f"🏛 **Rasmiy kanal:** @onatilidanyordam\n\n"
            "👇 *Testni yechish va umumiy reytingda qatnashish uchun bosing:*"
        )
        
        # Guruh a'zolari bosib to'g'ri botga o'tishi uchun inline tugma
        inline_markup = tele_types.InlineKeyboardMarkup()
        inline_markup.add(
            tele_types.InlineKeyboardButton(
                text="🚀 Testni boshlash (Reytingda qatnashish)",
                url=deep_link
            )
        )
        
        r = tele_types.InlineQueryResultArticle(
            id='quiz_share_card',
            title="🧠 Testni ushbu guruhga ulashish",
            description="Guruh a'zolari bilan birgalikda test ishlash va reytingda qatnashish",
            input_message_content=tele_types.InputTextMessageContent(
                message_text=message_content,
                parse_mode="Markdown",
                disable_web_page_preview=True
            ),
            reply_markup=inline_markup
        )
        
        bot.answer_inline_query(inline_query.id, [r], cache_time=1)
    except Exception as e:
        print(f"Inline query xatosi: {e}")

# --- ADMIN FOYDALANUVCHILAR BOSHQARUVI (SQLITE) ---
def get_users_page_markup(page=0, per_page=8):
    conn = get_db_connection()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_pages = max(1, (total_users + per_page - 1) // per_page)
    
    start_idx = page * per_page
    rows = conn.execute("SELECT * FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?", (per_page, start_idx)).fetchall()
    
    active_count = conn.execute("SELECT COUNT(*) FROM users WHERE status != 'blocked'").fetchone()[0]
    blocked_count = total_users - active_count
    conn.close()

    text = f"👥 **BOT FOYDALANUVCHILARI**\n"
    text += f"▫️ Jami: `{total_users}` | Faol: `{active_count}` | ❌ To'xtatgan: `{blocked_count}`\n"
    text += f"📄 Sahifa: `{page + 1}/{total_pages}`\n\n"

    markup = tele_types.InlineKeyboardMarkup(row_width=2)
    for idx, row in enumerate(rows, start=start_idx + 1):
        name = row["first_name"] or "Foydalanuvchi"
        uname = f"@{row['username']}" if row["username"] else "usernamesiz"
        st = "🟢" if row["status"] != "blocked" else "🔴"
        streak = row["streak"]
        points = row["points"]
        uid = row["user_id"]
        
        text += f"`{idx}.` {st} **{name}** ({uname})\n    └ ID: `{uid}` • 🔥 {streak} kun • `{points} ball`\n"
        btn_label = f"💬 {name[:12]}..." if len(name) > 12 else f"💬 {name}"
        markup.add(tele_types.InlineKeyboardButton(text=btn_label, callback_data=f"sendpm_{uid}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(tele_types.InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"usrpage_{page - 1}"))
    if page + 1 < total_pages:
        nav_btns.append(tele_types.InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"usrpage_{page + 1}"))
    if nav_btns:
        markup.row(*nav_btns)

    markup.add(
        tele_types.InlineKeyboardButton(text="📢 Hammaga umumiy xabar yo'llash", callback_data="admin_broadcast_start"),
        tele_types.InlineKeyboardButton(text="👤 ID orqali individual yozish", callback_data="admin_pm_manual")
    )
    markup.add(tele_types.InlineKeyboardButton(text="🔙 Boshqaruv menyusi", callback_data="admin_back_to_panel"))
    return text, markup

@bot.callback_query_handler(func=lambda call: call.data.startswith(("usrpage_", "sendpm_", "admin_broadcast_start", "admin_pm_manual", "admin_back_to_panel", "admin_view_users")))
def callback_admin_user_management(call):
    if int(call.from_user.id) != int(ADMIN_ID):
        bot.answer_callback_query(call.id, "Faqat bot administratori uchun!", show_alert=True)
        return

    data = call.data
    cid = call.message.chat.id
    mid = call.message.message_id

    if data == "admin_view_users":
        text, markup = get_users_page_markup(page=0)
        bot.edit_message_text(chat_id=cid, message_id=mid, text=text, parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data.startswith("usrpage_"):
        page = int(data.replace("usrpage_", ""))
        text, markup = get_users_page_markup(page=page)
        bot.edit_message_text(chat_id=cid, message_id=mid, text=text, parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data.startswith("sendpm_"):
        target_uid = int(data.replace("sendpm_", ""))
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (target_uid,)).fetchone()
        conn.close()
        u_name = row["first_name"] if row else "Foydalanuvchi"

        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            cid,
            f"✍️ **{u_name}** (`ID: {target_uid}`) ga yubormoqchi bo'lgan xabaringizni yozing:\n"
            "*(Bekor qilish uchun `/cancel` deb yozing)*",
            parse_mode="Markdown"
        )
        def forward_pm_text(m):
            if m.text.strip() == "/cancel":
                bot.send_message(cid, "❌ Xabar yuborish bekor qilindi.")
                return
            try:
                bot.send_message(
                    target_uid,
                    f"📬 **Bosh administrator xabarnomasi:**\n\n{m.text}\n\n"
                    f"🏛 **Rasmiy kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})",
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                bot.send_message(cid, f"✅ Xabar muvaffaqiyatli yetkazildi: `{target_uid}` ({u_name})", parse_mode="Markdown")
            except Exception as e:
                if "blocked by the user" in str(e):
                    conn_m = get_db_connection()
                    conn_m.execute("UPDATE users SET status = 'blocked' WHERE user_id = ?", (target_uid,))
                    conn_m.commit()
                    conn_m.close()
                bot.send_message(cid, f"❌ Xabarni yetkazib bo'lmadi: Foydalanuvchi botni bloklagan.")

        bot.register_next_step_handler(msg, forward_pm_text)

    elif data == "admin_pm_manual":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(cid, "👤 Foydalanuvchining **Telegram ID raqamini** kiriting:")
        def ask_id_step(m_id):
            target_id = m_id.text.strip()
            if not target_id.isdigit():
                bot.send_message(cid, "❌ Xato! ID raqami faqat sonlardan iborat bo'lishi lozim.")
                return
            msg_txt = bot.send_message(cid, f"✍️ `ID: {target_id}` ga yubormoqchi bo'lgan xabarni kiriting:")
            def send_direct_msg(m_text):
                try:
                    bot.send_message(
                        int(target_id),
                        f"📬 **Administrator xabarnomasi:**\n\n{m_text.text}\n\n"
                        f"🏛 **Rasmiy kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})",
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                    bot.send_message(cid, f"✅ Xabar muvaffaqiyatli yetkazildi (`{target_id}`)", parse_mode="Markdown")
                except Exception:
                    conn_m = get_db_connection()
                    conn_m.execute("UPDATE users SET status = 'blocked' WHERE user_id = ?", (int(target_id),))
                    conn_m.commit()
                    conn_m.close()
                    bot.send_message(cid, f"❌ Yetkazib bo'lmadi: Foydalanuvchi botni bloklagan.")
            bot.register_next_step_handler(msg_txt, send_direct_msg)
        bot.register_next_step_handler(msg, ask_id_step)

    elif data == "admin_broadcast_start":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            cid,
            "📢 **Barcha bot foydalanuvchilariga umumiy xabar (Broadcast):**\n\n"
            "Yubormoqchi bo'lgan xabaringiz matnini kiriting:\n"
            "*(Bekor qilish uchun `/cancel` deb yozing)*",
            parse_mode="Markdown"
        )
        def broadcast_step(m):
            if m.text.strip() == "/cancel":
                bot.send_message(cid, "❌ Bekor qilindi.")
                return
            
            conn_b = get_db_connection()
            user_ids = [row["user_id"] for row in conn_b.execute("SELECT user_id FROM users").fetchall()]
            conn_b.close()
            
            success = 0
            blocked = 0
            bot.send_message(cid, f"🚀 {len(user_ids)} ta a'zoga xabar yo'llash boshlandi...")
            
            conn_up = get_db_connection()
            for uid_key in user_ids:
                try:
                    bot.send_message(
                        uid_key,
                        f"📢 **Umumiy E'lon:**\n\n{m.text}\n\n"
                        f"🏛 **Rasmiy kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})",
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                    success += 1
                    conn_up.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (uid_key,))
                    time.sleep(0.04)
                except Exception as ex:
                    if "blocked by the user" in str(ex):
                        conn_up.execute("UPDATE users SET status = 'blocked' WHERE user_id = ?", (uid_key,))
                        blocked += 1
            conn_up.commit()
            conn_up.close()
            
            bot.send_message(
                cid, 
                f"✅ **Tarqatish yakunlandi!**\n\n"
                f"▫️ Yetkazildi: `{success} ta`\n"
                f"▫️ Botni bloklaganlar: `{blocked} ta`", 
                parse_mode="Markdown"
            )
        bot.register_next_step_handler(msg, broadcast_step)

    elif data == "admin_back_to_panel":
        conn_p = get_db_connection()
        total_u = conn_p.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_u = conn_p.execute("SELECT COUNT(*) FROM users WHERE status != 'blocked'").fetchone()[0]
        blocked_u = total_u - active_u
        conn_p.close()

        results = load_data(RESULTS_FILE)
        ch_count = bot.get_chat_member_count(CHANNEL_USERNAME)

        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="👥 Foydalanuvchilar ro'yxatini ko'rish", callback_data="admin_view_users"),
            tele_types.InlineKeyboardButton(text="📢 Barcha a'zolarga umumiy xabar yo'llash", callback_data="admin_broadcast_start"),
            tele_types.InlineKeyboardButton(text="👤 Individual xabar yuborish", callback_data="admin_pm_manual"),
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi (Mini-App)", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            )
        )
        bot.edit_message_text(
            chat_id=cid,
            message_id=mid,
            text=(
                f"📊 **BOSHQARUV VA STATISTIKA PANELI (ADMIN):**\n\n"
                f"▫️ Jami ro'yxatdan o'tganlar: `{total_u} nafar`\n"
                f"▫️ Faol foydalanuvchilar: `{active_u} nafar`\n"
                f"▫️ Botni to'xtatganlar: `{blocked_u} nafar`\n"
                f"▫️ Test topshirganlar: `{len(results)} nafar`\n"
                f"▫️ Rasmiy kanal a'zolari: `{ch_count} nafar`\n\n"
                "Quyidagi boshqaruv amallaridan birini tanlang:"
            ),
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)

@bot.message_handler(commands=['send'])
def cmd_broadcast(message):
    if int(message.from_user.id) != int(ADMIN_ID):
        return
    text_to_send = message.text.replace("/send", "").strip()
    if not text_to_send:
        bot.reply_to(message, "Xabar matnini kiriting. Masalan: `/send Yangi test qo'shildi!`", parse_mode="Markdown")
        return

    conn = get_db_connection()
    user_ids = [row["user_id"] for row in conn.execute("SELECT user_id FROM users").fetchall()]
    
    success = 0
    blocked = 0
    bot.reply_to(message, f"📢 {len(user_ids)} ta a'zoga xabar yo'llash boshlandi...")
    for uid_key in user_ids:
        try:
            bot.send_message(
                uid_key,
                f"📢 **Umumiy E'lon:**\n\n{text_to_send}\n\n"
                f"🏛 **Rasmiy kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            success += 1
            conn.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (uid_key,))
            time.sleep(0.04)
        except Exception as ex:
            if "blocked by the user" in str(ex):
                conn.execute("UPDATE users SET status = 'blocked' WHERE user_id = ?", (uid_key,))
                blocked += 1
    conn.commit()
    conn.close()
    bot.send_message(
        message.chat.id, 
        f"✅ **Tarqatish yakunlandi!**\n\n▫️ Yetkazildi: `{success} ta`\n▫️ Botni to'xtatganlar: `{blocked} ta`", 
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['pm'])
def cmd_send_pm(message):
    if int(message.from_user.id) != int(ADMIN_ID):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "Foydalanish: `/pm USER_ID xabar matni`", parse_mode="Markdown")
        return
    
    target_id = parts[1].strip()
    pm_text = parts[2].strip()

    try:
        bot.send_message(
            int(target_id),
            f"📬 **Bosh administrator xabarnomasi:**\n\n{pm_text}\n\n"
            f"🏛 **Rasmiy kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        bot.reply_to(message, f"✅ Xabar `{target_id}` ga yetkazildi!", parse_mode="Markdown")
    except Exception:
        conn = get_db_connection()
        conn.execute("UPDATE users SET status = 'blocked' WHERE user_id = ?", (int(target_id),))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"❌ Foydalanuvchi botni bloklagan.")

def auto_poster_loop():
    tz = pytz.timezone('Asia/Tashkent')
    sent_flags = {"08:30": False, "20:30": False}

    while True:
        try:
            now = datetime.now(tz)
            current_time = now.strftime("%H:%M")

            if current_time == "00:01":
                for k in sent_flags:
                    sent_flags[k] = False

            if current_time == "08:30" and not sent_flags["08:30"]:
                hikmat_full = get_verified_didactic_content("hikmat")
                clean_text = hikmat_full.split("📚 Aniq manba:")[0].strip()
                channel_post = f"☀️ **TONGGI HIKMAT & ILMIY TAFAKKUR**\n\n{clean_text}\n\n───────────────\n🌟 **Rasmiy kanal:** [{CHANNEL_USERNAME}]({CHANNEL_URL})"
                bot.send_message(CHANNEL_USERNAME, channel_post, parse_mode="Markdown", disable_web_page_preview=True)
                sent_flags["08:30"] = True

            elif current_time == "20:30" and not sent_flags["20:30"]:
                bot.send_message(CHANNEL_USERNAME, "🧠 **KECHKI INTELLEKT: BMB TEST SINOVI**\n\nBugungi bilimlaringizni sinab ko'ring:")
                for _ in range(3):
                    try:
                        p_single = (
                            "BMB (DTM) standarti bo'yicha 5-11-sinf Ona tili va adabiyot darsliklaridan 1 ta 100% xatosiz Quiz test tuzing. "
                            "Diniy va siyosiy mavzulardan mutlaqo chetlaning. Faqat JSON formatida javob bering:\n"
                            "{\n"
                            '  "question": "Savol matni",\n'
                            '  "options": ["A", "B", "C", "D"],\n'
                            '  "correct_option_id": 0,\n'
                            '  "explanation": "Qisqa ilmiy izoh"\n'
                            "}"
                        )
                        raw = ai_client.models.generate_content(
                            model="gemini-3.6-flash",
                            contents=p_single,
                            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.3)
                        ).text.strip()
                        if "```json" in raw:
                            raw = raw.split("```json")[1].split("```")[0].strip()
                        elif "```" in raw:
                            raw = raw.split("```")[1].split("```")[0].strip()
                        q_obj = json.loads(raw)
                        bot.send_poll(
                            chat_id=CHANNEL_USERNAME,
                            question=f"⏳ {q_obj['question'][:280]}",
                            options=[opt[:95] for opt in q_obj["options"][:4]],
                            type="quiz",
                            correct_option_id=q_obj["correct_option_id"],
                            explanation=f"{q_obj.get('explanation', '')}\n👉 @onatilidanyordam"[:190],
                            is_anonymous=False
                        )
                        time.sleep(3)
                    except Exception:
                        pass
                sent_flags["20:30"] = True

            time.sleep(30)
        except Exception as e:
            print(f"Auto-posting xatosi: {e}")
            time.sleep(30)

threading.Thread(target=auto_poster_loop, daemon=True).start()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    streak, points, streak_broken = update_user_streak(message.from_user)

    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    streak_msg = ""
    if streak_broken:
        streak_msg = "\n⚠️ *Siz kecha botga kirmaganingiz sababli olovli seriyangiz uzildi va qaytadan boshlandi! Har kuni kirib turishni unutmang.*\n"
    else:
        streak_msg = f"\n🔥 **Olovli seriya:** `{streak} kun davom etmoqda!` (+25 XP olindi)\n"

    user_name = message.from_user.first_name or "Foydalanuvchi"
    text = (
        f"╭──── ✨ **Assalomu alaykum, {user_name}!** ────╮\n\n"
        f"🏛 **AI TILSHUNOS & METODIST (v11.3 - Full Pro Edition)** portaliga xush kelibsiz!\n"
        f"{streak_msg}\n"
        "Quyidagi asosiy yo'nalishlardan birini tanlang:\n\n"
        "🎓 **Talabalar uchun:** Mumtoz meros, aruz, qadimgi til va etimologiya\n"
        "👨‍🏫 **O'qituvchilar uchun:** Konspektlar, metodlar va Attestatsiya testlari\n"
        "🎒 **Abituriyentlar uchun:** Milliy sertifikat esselari, O'TIL, BMB va Mavzuli testlar\n"
        "🛠 **Quiz Test Tuzuvchi:** O'zingiz xohlagan mavzuda professional test yasash\n"
        "🔬 **Ilmiy izlanuvchilar uchun:** OAK maqola va tezis loyihalash\n\n"
        "👇 *Yo'nalishingizni tanlang:* \n"
        "╰─────────────────────────────────────╯"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data in ["check_sub"])
def callback_check_sub(call):
    update_user_streak(call.from_user)
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "🎉 Obuna tasdiqlandi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    update_user_streak(message.from_user)

    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = message.text
    u_id = message.from_user.id
    is_admin = (int(u_id) == int(ADMIN_ID))

    if text == "🔙 Asosiy menyu":
        bot.send_message(message.chat.id, "📋 Asosiy toifalardan birini tanlang:", reply_markup=get_main_menu(u_id))
        return

    elif text == "👤 Shaxsiy kabinet":
        show_user_profile(message.chat.id, message.from_user)

    elif text == "🏆 Jonli Reyting Doskasi":
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi (Mini-App)", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            )
        )
        bot.send_message(
            message.chat.id, 
            "🏆 **BMB VA MILLIY SERTIFIKAT JONLI REYTINGI**\n\n"
            "Quyidagi tugma orqali reyting doskasini ko'rishingiz mumkin:", 
            reply_markup=markup
        )

    elif text == "🛠 Quiz Test Tuzuvchi":
        send_quiz_creator_hub(message.chat.id)

    elif text == "🎓 Talabalar uchun":
        send_section_card(message.chat.id, "talaba")

    elif text == "👨‍🏫 O'qituvchilar uchun":
        send_section_card(message.chat.id, "oqituvchi")

    elif text == "🎒 Abituriyentlar uchun":
        send_section_card(message.chat.id, "abituriyent")

    elif text == "🔬 Ilmiy izlanuvchilar uchun":
        send_section_card(message.chat.id, "izlanuvchi")

    elif text == "📊 Boshqaruv & Statistika" and is_admin:
        conn = get_db_connection()
        total_u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_u = conn.execute("SELECT COUNT(*) FROM users WHERE status != 'blocked'").fetchone()[0]
        blocked_u = total_u - active_u
        conn.close()

        results = load_data(RESULTS_FILE)
        ch_count = bot.get_chat_member_count(CHANNEL_USERNAME)

        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="👥 Foydalanuvchilar ro'yxatini ko'rish", callback_data="admin_view_users"),
            tele_types.InlineKeyboardButton(text="📢 Barcha a'zolarga umumiy xabar yo'llash", callback_data="admin_broadcast_start"),
            tele_types.InlineKeyboardButton(text="👤 Individual xabar yuborish", callback_data="admin_pm_manual"),
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi (Mini-App)", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            )
        )

        bot.send_message(
            message.chat.id,
            f"📊 **BOSHQARUV VA STATISTIKA PANELI (ADMIN):**\n\n"
            f"▫️ Jami ro'yxatdan o'tganlar: `{total_u} nafar`\n"
            f"▫️ Faol foydalanuvchilar: `{active_u} nafar`\n"
            f"▫️ Botni to'xtatganlar (bloklaganlar): `{blocked_u} nafar`\n"
            f"▫️ Test topshirganlar: `{len(results)} nafar`\n"
            f"▫️ Rasmiy kanal a'zolari: `{ch_count} nafar`\n\n"
            "Kerakli amaliyotni tanlang:",
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
                f"💡 *Kanalga chiqarilsa manba qismi avtomatik olib tashlanadi va faqat rasmiy kanal havolasi qo'yiladi.*",
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
                f"💡 *Kanalga chiqarilsa manba qismi avtomatik olib tashlanadi va faqat rasmiy kanal havolasi qo'yiladi.*",
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xatolik: {e}")

    else:
        bot.send_message(message.chat.id, "Iltimos, pastdagi menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu(u_id))

print("AI Tilshunos v11.3 (Full Pro Edition) faol ishga tushdi...")
bot.infinity_polling()

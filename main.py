import os
import threading
import json
import random
import time
from datetime import datetime
import pytz
import requests
from flask import Flask
import telebot
from telebot import types as tele_types
from google import genai
from google.genai import types

# --- RENDER WEB SERVICE UCHUN SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "AI Tilshunos & Metodist v8.0 (30-Quiz Leaderboard Edition) Faol!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- SERVERNI UYG'OQ SAQLASH (SELF-PING) ---
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

USERS_FILE = "users.json"
RESULTS_FILE = "test_results.json"

# Foydalanuvchilarning ayni paytdagi faol test sessiyasi
# {user_id: {"questions": [...], "current_index": 0, "correct_count": 0, "start_time": ..., "poll_id": ...}}
USER_QUIZ_SESSIONS = {}
POLL_TO_USER_MAP = {}

IMZO = (
    "\n\n╭───────────────────────╮\n"
    f"  🏛 **Kanal:** {CHANNEL_USERNAME}\n"
    "  ✨ **AI Asistent:** @aitilshunosbot\n"
    "╰───────────────────────╯"
)

# --- XAVFSIZLIK FILTRI ---
FORBIDDEN_KEYWORDS = [
    "prezident", "mirziyoyev", "hokim", "vazir", "hukumat", "davlat boshqaruvi", 
    "siyosat", "saylov", "muxolifat", "deputat", "amaldor", "partiya",
    "din", "islom", "namoz", "hadis", "oyat", "qur'on", "shariat", "masjid",
    "xristian", "cherkov", "yahudiy", "fatvo", "ro'za", "mulla", "imom",
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
    "╭─ ⚠️ **ETIKA VA ME'YOR BILDIRISHNOMASI** ─╮\n\n"
    "Platforma faqat **tilshunoslik, adabiyotshunoslik va metodika** "
    "bo'yicha ilmiy yordamchi hisoblanadi.\n\n"
    "> *Diniy, siyosiy, amaldagi davlat boshqaruvi hamda inson qadr-qimmatini kamsituvchi har qanday so'rovlar qat'iyan taqiqlanadi!*\n\n"
    "╰─────────────────────────────────────╯"
)

# --- MA'LUMOTLAR BAZASINI BOSHQARISH ---
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
    except Exception as e:
        print(f"Faylni saqlashda xato ({filepath}): {e}")

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

def save_test_result(user_id, user_name, correct_count, duration_seconds):
    results = load_data(RESULTS_FILE)
    u_id = str(user_id)
    
    # Foydalanuvchining eng yaxshi natijasi saqlanadi
    current_best = results.get(u_id, {"correct": -1, "duration": 999999})
    if (correct_count > current_best.get("correct", -1)) or (correct_count == current_best.get("correct", -1) and duration_seconds < current_best.get("duration", 999999)):
        results[u_id] = {
            "name": user_name,
            "correct": correct_count,
            "duration": duration_seconds,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_data(RESULTS_FILE, results)

def get_leaderboard_position(user_id):
    results = load_data(RESULTS_FILE)
    if not results:
        return 1, 1, []

    # Saralash: to'g'ri javoblar ko'p bo'yicha, teng bo'lsa vaqti kamroq bo'yicha
    sorted_users = sorted(
        results.items(),
        key=lambda x: (-x[1]["correct"], x[1]["duration"])
    )

    total_participants = len(sorted_users)
    user_rank = 1
    for idx, (uid, info) in enumerate(sorted_users, 1):
        if str(uid) == str(user_id):
            user_rank = idx
            break

    top_10 = sorted_users[:10]
    return user_rank, total_participants, top_10

# --- MENYULAR TUZILISHI ---
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
        markup.row(tele_types.KeyboardButton("📊 Boshqaruv & Statistika"))
    return markup

def get_group_menu(group_name):
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if group_name == "talaba":
        markup.row(tele_types.KeyboardButton("📜 G'azal tahlili"), tele_types.KeyboardButton("📐 Aruz vazni hisoblagich"))
        markup.row(tele_types.KeyboardButton("🏛 Qadimgi turkiy til"), tele_types.KeyboardButton("🔍 So'z etimologiyasi"))
    elif group_name == "oqituvchi":
        markup.row(tele_types.KeyboardButton("📋 Dars ishlanmasi"), tele_types.KeyboardButton("🎯 Interfaol metodlar"))
    elif group_name == "abituriyent":
        markup.row(tele_types.KeyboardButton("📝 Esse tekshiruvi (50 ball)"), tele_types.KeyboardButton("📖 So'z izohi (O'TIL)"))
        markup.row(tele_types.KeyboardButton("🔤 Imlo va orfoepiya"), tele_types.KeyboardButton("🧠 BMB 30 talik Test"))
    elif group_name == "izlanuvchi":
        markup.row(tele_types.KeyboardButton("📑 Ilmiy maqola (OAK)"), tele_types.KeyboardButton("📄 Ilmiy tezis (Konferensiya)"))
    
    markup.row(tele_types.KeyboardButton("🔙 Asosiy menyu"))
    return markup

def get_sub_menu(category):
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    labels = {
        "maqola": ("✍️ Mavzuni kiritish", "🎲 Tasodifiy mavzu rejasi"),
        "tezis": ("✍️ Tezis mavzusini kiritish", "🎲 Tasodifiy tezis rejasi"),
        "konspekt": ("✍️ Mavzuni kiritaman", "🎲 Namunaviy dars ishlanmasi"),
        "esse": ("✍️ Esseni yuborish", "🎲 Namunaviy esse tahlili"),
        "metod": ("✍️ Mavzuni kiritaman", "🎲 Tasodifiy metod"),
        "gazal": ("✍️ Baytni yuborish", "🎲 Tasodifiy mumtoz bayt"),
        "aruz": ("✍️ Bayt kiritish", "🎲 Namunaviy aruz tahlili"),
        "qadim": ("✍️ Tarixiy so'zni kiritish", "🎲 Tasodifiy qadimgi so'z"),
        "izoh": ("✍️ So'zni kiritish", "🎲 Tasodifiy O'TIL so'zi"),
        "etimologiya": ("✍️ So'zni kiritish", "🎲 Tasodifiy etimologiya"),
        "imlo": ("✍️ So'z/jumlani kiritish", "🎲 Ko'p adashiladigan so'z"),
        "bmb_test": ("🚀 30 talik testni boshlash", "🏆 Reyting jadvali")
    }
    btn1, btn2 = labels.get(category, ("✍️ O'zim kiritaman", "🎲 Tasodifiy"))
    markup.row(tele_types.KeyboardButton(btn1), tele_types.KeyboardButton(btn2))
    markup.row(tele_types.KeyboardButton("🔙 Asosiy menyu"))
    return markup

def get_action_inline():
    markup = tele_types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        tele_types.InlineKeyboardButton(text="📢 Kanalimiz", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
        tele_types.InlineKeyboardButton(text="✨ Yangi so'rov", callback_data="refresh_menu")
    )
    return markup

# --- NATIJANI YUBORISH ---
def deliver_response(user_id, text):
    if len(text) > 3900:
        parts = [text[i:i+3900] for i in range(0, len(text), 3900)]
    else:
        parts = [text]

    is_admin = False
    try:
        if int(user_id) == int(ADMIN_ID):
            is_admin = True
    except Exception:
        pass

    for part in parts:
        if is_admin:
            try:
                bot.send_message(CHANNEL_USERNAME, part, parse_mode="Markdown")
                bot.send_message(user_id, part, parse_mode="Markdown", reply_markup=get_action_inline())
            except Exception:
                bot.send_message(user_id, part, reply_markup=get_action_inline())
        else:
            try:
                bot.send_message(user_id, part, parse_mode="Markdown", reply_markup=get_action_inline())
            except Exception:
                bot.send_message(user_id, part, reply_markup=get_action_inline())

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

# --- GEMINI SISTEMA YO'RIQNOMASI ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi OAK eksperti, filolog-matnshunos olim va BMB (DTM) "
    "hamda umumta'lim maktablari bo'yicha bosh metodistsiz.\n\n"
    "QAT'IY CHEKLOV: Ilmiy maqola va tezis so'ralganda TAYYOR MATN YOZMANG! "
    "Faqat muallif mustaqil yoza olishi uchun: puxta ilmiy reja, ilmiy apparat (maqsad, vazifa, dolzarblik), "
    "metodologiya va OAK talabidagi adabiyotlar yo'nalishini bering.\n\n"
    "XAVFSIZLIK: Diniy, siyosiy, davlat boshqaruvi va amaldorlar shaxsi, shuningdek haqoratli mavzular qat'iyan taqiqlanadi.\n\n"
    "BMB TEST MEZONI: 5-11-sinf tasdiqlangan ona tili va adabiyot darsliklari asosida tuzilsin."
)

# --- AI GENERATSIYA FUNKSIYASI ---
def generate_ai_content(prompt_text, chat_id=None):
    if check_security_violation(prompt_text):
        return SECURITY_WARNING

    if chat_id:
        try:
            bot.send_chat_action(chat_id, 'typing')
        except Exception:
            pass

    full_prompt = (
        f"{prompt_text}\n\n"
        "Talablar: Telegram Markdown formatida, ko'rkam sarlavhalar va ilmiy uslubda, darslik standartida bo'lsin. "
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

# --- 30 TALIK BMB TEST SAVOLLARINI GENERATSIYA QILISH (JSON RO'YXAT) ---
def generate_30_quiz_questions(chat_id):
    try:
        bot.send_chat_action(chat_id, 'typing')
    except Exception:
        pass

    random_seed = random.randint(10000, 99999)
    prompt = (
        f"O'zbekiston Respublikasi BMB (DTM) va Milliy sertifikat rasmiy imtihon standarti asosida "
        f"tasdiqlangan 5-11-sinf Ona tili va adabiyoti darsliklaridan TO'LIQ 30 TA original Quiz test tuzing (Seed #{random_seed}).\n\n"
        "SAVOLLARNING QAT'IY MAVZU TAQSIMOTI:\n"
        "1-4: Fonetika, orfoepiya, imlo qoidalari;\n"
        "5-8: Leksikologiya, frazeologiya, paronimlar, shakldosh va ma'nodosh so'zlar;\n"
        "9-14: Morfologiya (so'z turkumlari, qo'shimchalar, fe'l shakllari, yordamchilar);\n"
        "15-18: Sintaksis (gap bo'laklari, ergashgan qo'shma gaplar, tinish belgilari);\n"
        "19-22: Matn mantiqiy tahlili va uslubiyat;\n"
        "23-26: Mumtoz adabiyot (Navoiy, Bobur, aruz vazni, badiiy san'atlar: tazod, tanosub, istiora);\n"
        "27-30: Jadid va XX asr o'zbek adabiyoti (Cho'lpon, Fitrat, Qodiriy, Oybek asarlari).\n\n"
        "Javobni FAQAT quyidagi JSON formatida qaytaring (hech qanday qo'shimcha so'zsiz):\n"
        "[\n"
        "  {\n"
        '    "question": "1-savol matni (maksimal 250 belgi)",\n'
        '    "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '    "correct_option_id": 0,\n'
        '    "explanation": "Qisqa izoh va darslik manbasi (maksimal 180 belgi)"\n'
        "  }\n"
        "]\n"
        "DIQQAT: Ro'yxatda aniq 30 ta savol obyekti bo'lsin. Variantlar uzunligi 100 belgidan oshmasin."
    )

    models = ["gemini-3.6-flash"]
    last_error = ""
    for model_name in models:
        for attempt in range(3):
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
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
                if isinstance(questions, list) and len(questions) >= 25:
                    return questions[:30]
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
    raise Exception(f"30 talik test tayyorlashda xatolik: {last_error[:300]}")

# --- KEYINGI QUIZ TESTNI YUBORISH ---
def send_next_quiz_poll(user_id):
    session = USER_QUIZ_SESSIONS.get(user_id)
    if not session:
        return

    idx = session["current_index"]
    questions = session["questions"]

    # Agar 30 ta savol tugagan bo'lsa: Natija va reytingni hisoblash
    if idx >= len(questions):
        finish_quiz_session(user_id)
        return

    q_data = questions[idx]
    q_num = idx + 1
    total_q = len(questions)

    question_title = f"[{q_num}/{total_q}] {q_data['question']}"
    if len(question_title) > 295:
        question_title = question_title[:292] + "..."

    # Variantlar uzunligini tekshirish (Telegram limiti: 100 belgi)
    cleaned_options = [opt[:98] for opt in q_data["options"][:4]]
    correct_id = int(q_data.get("correct_option_id", 0))
    if correct_id not in [0, 1, 2, 3]:
        correct_id = 0

    explanation = q_data.get("explanation", "")[:195]

    try:
        poll_msg = bot.send_poll(
            chat_id=user_id,
            question=question_title,
            options=cleaned_options,
            type="quiz",
            correct_option_id=correct_id,
            explanation=explanation,
            is_anonymous=False
        )
        session["poll_id"] = poll_msg.poll.id
        session["correct_option_id"] = correct_id
        POLL_TO_USER_MAP[poll_msg.poll.id] = user_id
    except Exception as e:
        print(f"Poll yuborishda xato: {e}")
        # Agar savolda xato bo'lsa, keyingisiga o'tkazish
        session["current_index"] += 1
        send_next_quiz_poll(user_id)

# --- QUIZ JAVOBLARINI TUTIB OLISH (POLL ANSWER HANDLER) ---
@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    poll_id = poll_answer.poll_id
    user_id = POLL_TO_USER_MAP.get(poll_id)
    if not user_id or user_id not in USER_QUIZ_SESSIONS:
        return

    session = USER_QUIZ_SESSIONS[user_id]
    selected_option = poll_answer.option_ids[0]
    correct_option = session.get("correct_option_id", 0)

    if selected_option == correct_option:
        session["correct_count"] += 1

    session["current_index"] += 1
    POLL_TO_USER_MAP.pop(poll_id, None)

    # 1.5 soniyadan so'ng keyingi savolga o'tish
    time.sleep(1.2)
    send_next_quiz_poll(user_id)

# --- TEST YAKUNLANDI: NATIJA VA EGALLAGAN O'RNI ---
def finish_quiz_session(user_id):
    session = USER_QUIZ_SESSIONS.pop(user_id, None)
    if not session:
        return

    total_q = len(session["questions"])
    correct = session["correct_count"]
    incorrect = total_q - correct
    percentage = round((correct / total_q) * 100, 1)

    duration = int(time.time() - session["start_time"])
    minutes = duration // 60
    seconds = duration % 60
    time_str = f"{minutes} daqiqa {seconds} soniya"

    user_name = session.get("name", "Ishtirokchi")
    save_test_result(user_id, user_name, correct, duration)

    user_rank, total_participants, top_10 = get_leaderboard_position(user_id)

    # Top-10 reyting jadvali matni
    leaderboard_text = ""
    for idx, (uid, info) in enumerate(top_10, 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        m_dur = info['duration'] // 60
        s_dur = info['duration'] % 60
        leaderboard_text += f"{medal} **{info['name']}** — `{info['correct']}/{total_q}` ({m_dur}m {s_dur}s)\n"

    result_message = (
        "╔════════════════════════════════╗\n"
        "  🏆 **TEST SINOVI MUVAFFAQIYATLI YAKUNLANDI!**\n"
        "╚════════════════════════════════╝\n\n"
        f"👤 **Ishtirokchi:** {user_name}\n"
        f"⏱ **Sarflangan vaqt:** {time_str}\n\n"
        "📊 **SIZNING NATIJANGIZ:**\n"
        f"✅ To'g'ri javoblar: `{correct} ta`\n"
        f"❌ Noto'g'ri javoblar: `{incorrect} ta`\n"
        f"📈 O'zlashtirish ko'rsatkichi: `{percentage}%`\n\n"
        "────────────────────────────────\n"
        f"🎖 **EGALLAGAN O'RNINGIZ: #{user_rank}-o'rin**\n"
        f"👥 *Jami ishtirokchilar soni: {total_participants} nafar*\n"
        "────────────────────────────────\n\n"
        "🏆 **ENG YAXSHI ISHTIROKCHILAR (TOP REYTING):**\n"
        f"{leaderboard_text}\n"
        "💡 *BMB standartidagi yangi testlarni yana topshirishingiz mumkin!*"
    )

    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(tele_types.KeyboardButton("🚀 30 talik testni boshlash"), tele_types.KeyboardButton("🏆 Reyting jadvali"))
    markup.row(tele_types.KeyboardButton("🔙 Asosiy menyu"))

    bot.send_message(user_id, result_message, parse_mode="Markdown", reply_markup=markup)

# --- REYTING JADVALINI ALOHIDA KO'RISH ---
def show_leaderboard(chat_id):
    results = load_data(RESULTS_FILE)
    if not results:
        bot.send_message(chat_id, "Hozircha test ishtirokchilari mavjud emas. Birinchi bo'lib testni boshlang!")
        return

    sorted_users = sorted(results.items(), key=lambda x: (-x[1]["correct"], x[1]["duration"]))[:15]
    leaderboard_text = ""
    for idx, (uid, info) in enumerate(sorted_users, 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`{idx}.`"
        m_dur = info['duration'] // 60
        s_dur = info['duration'] % 60
        leaderboard_text += f"{medal} **{info['name']}** — `{info['correct']}/30` ({m_dur}m {s_dur}s)\n"

    msg = (
        "╭─── 🏆 **BMB 30 TALIK TEST REYTINGI** ───╮\n\n"
        f"{leaderboard_text}\n"
        f"👥 *Jami ishtirokchilar:* `{len(results)} nafar`\n"
        "╰─────────────────────────────────────╯"
    )
    bot.send_message(chat_id, msg, parse_mode="Markdown")

# --- KANAL UCHUN AVTOPOSTING QUIZ ---
def generate_ai_quiz():
    random_seed = random.randint(1000, 99999)
    prompt = (
        f"BMB standarti asosida tasdiqlangan darsliklardan 1 ta original Quiz test (Seed #{random_seed}) tuzing. "
        "Diniy va siyosiy mavzulardan mutlaqo chetlaning. Faqat quyidagi JSON formatida javob bering:\n"
        "{\n"
        '  "question": "Savol matni",\n'
        '  "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob izohi va darslik manbasi (180 belgidan oshmasin)"\n'
        "}\n"
        "correct_option_id 0, 1, 2 yoki 3 bo'lsin."
    )
    models = ["gemini-3.6-flash"]
    for model_name in models:
        try:
            response = ai_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.8
                )
            )
            raw = response.text.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            return json.loads(raw)
        except Exception:
            pass
    raise Exception("Quiz tayyorlashda xatolik yuz berdi.")

def auto_poster_loop():
    tz = pytz.timezone('Asia/Tashkent')
    sent_flags = {"08:30": False, "13:00": False, "17:00": False, "20:30": False}

    while True:
        try:
            now = datetime.now(tz)
            current_time = now.strftime("%H:%M")

            if current_time == "00:01":
                for k in sent_flags:
                    sent_flags[k] = False

            if current_time == "08:30" and not sent_flags["08:30"]:
                p = "Alisher Navoiy, Bobur yoki mumtoz allomalarimiz asarlaridan ilm, odob va til madaniyati haqida ibratli tonggi post tayyorlang."
                matn = generate_ai_content(p)
                bot.send_message(CHANNEL_USERNAME, f"☀️ **KUN HIKMATI & ILMIY TAFAKKUR**\n\n{matn}", parse_mode="Markdown")
                sent_flags["08:30"] = True

            elif current_time == "13:00" and not sent_flags["13:00"]:
                p = "O'zbek tilining izohli lug'ati yoki etimologik lug'at asosida bitta qiziqarli so'zning chuqur filologik tahlilini taqdim eting."
                matn = generate_ai_content(p)
                bot.send_message(CHANNEL_USERNAME, f"📖 **KUN SO'ZI TAHLILI**\n\n{matn}", parse_mode="Markdown")
                sent_flags["13:00"] = True

            elif current_time == "17:00" and not sent_flags["17:00"]:
                p = "Ona tili yoki adabiyot darslari uchun zamonaviy interfaol metod ishlab chiqing: Mavzu, Metod nomi, Darsdagi o'rni, Bosqichlari va Tavsiyalar."
                matn = generate_ai_content(p)
                bot.send_message(CHANNEL_USERNAME, f"🎯 **METODIK MAHORAT RUKNI**\n\n{matn}", parse_mode="Markdown")
                sent_flags["17:00"] = True

            elif current_time == "20:30" and not sent_flags["20:30"]:
                bot.send_message(CHANNEL_USERNAME, "🧠 **KECHKI INTELLEKT: BMB TEST SINOVI**")
                for _ in range(3):
                    try:
                        q = generate_ai_quiz()
                        bot.send_poll(
                            chat_id=CHANNEL_USERNAME,
                            question=q["question"],
                            options=q["options"],
                            type="quiz",
                            correct_option_id=q["correct_option_id"],
                            explanation=q.get("explanation", ""),
                            is_anonymous=True
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

# --- ADMIN STATISTIKASI ---
def show_admin_stats(chat_id):
    users = load_data(USERS_FILE)
    total_users = len(users)
    results = load_data(RESULTS_FILE)
    total_tested = len(results)

    channel_members = "Aniqlanmadi"
    try:
        channel_members = bot.get_chat_member_count(CHANNEL_USERNAME)
    except Exception:
        pass

    last_users_text = ""
    for idx, (uid, data) in enumerate(list(users.items())[-8:], 1):
        uname = f"@{data['username']}" if data.get("username") else "usernamesiz"
        fname = data.get("first_name", "Foydalanuvchi")
        date_str = data.get("date", "")
        last_users_text += f"`{idx}.` {fname} ({uname}) • `{uid}`\n"

    if not last_users_text:
        last_users_text = "_Hozircha foydalanuvchilar mavjud emas._"

    msg = (
        "╭─── 📊 **ADMINISTRATOR BOSHQARUV PANELI** ───╮\n\n"
        f"▫️ **Bot a'zolari:** `{total_users}` nafar\n"
        f"▫️ **30 talik test topshirganlar:** `{total_tested}` nafar\n"
        f"▫️ **Kanal auditoriyasi:** `{channel_members}` obunachi\n\n"
        "👥 **Oxirgi faol a'zolar:**\n"
        f"{last_users_text}\n"
        "📢 *Barcha a'zolarga xabar yuborish:* `/send xabar matni`\n"
        "╰──────────────────────────────────────────╯"
    )
    bot.send_message(chat_id, msg, parse_mode="Markdown")

# --- ADMIN BUYRUQLARI ---
@bot.message_handler(commands=['stat'])
def cmd_stat(message):
    if int(message.from_user.id) == int(ADMIN_ID):
        show_admin_stats(message.chat.id)
    else:
        bot.reply_to(message, "Ushbu buyruq faqat bot administratori uchun.")

@bot.message_handler(commands=['send'])
def broadcast_message(message):
    if int(message.from_user.id) != int(ADMIN_ID):
        return
    text_to_send = message.text.replace("/send", "").strip()
    if not text_to_send:
        bot.reply_to(message, "Xabar matnini kiriting. Masalan: `/send Yangilik!`", parse_mode="Markdown")
        return

    users = load_data(USERS_FILE)
    success = 0
    bot.reply_to(message, f"📢 {len(users)} ta a'zoga xabar yo'llash boshlandi...")
    for uid in users.keys():
        try:
            bot.send_message(uid, text_to_send)
            success += 1
            time.sleep(0.05)
        except Exception:
            pass
    bot.send_message(message.chat.id, f"✅ Xabar tarqatildi!\nQabul qildi: {success} ta foydalanuvchi.")

@bot.message_handler(commands=['myid'])
def get_user_id(message):
    bot.reply_to(message, f"🆔 Sizning Telegram ID raqamingiz: `{message.from_user.id}`", parse_mode="Markdown")

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
        "🏛 **AI TILSHUNOS & METODIST (v8.0)** portaliga xush kelibsiz!\n\n"
        "Qulaylik yaratish maqsadida bot xizmatlari 4 asosiy yo'nalishga ajratildi:\n\n"
        "🎓 **Talabalar uchun:** Mumtoz meros, aruz, qadimgi til va etimologiya\n"
        "👨‍🏫 **O'qituvchilar uchun:** 45 daqiqalik konspekt va zamonaviy metodlar\n"
        "🎒 **Abituriyentlar uchun:** 50 ballik esse, O'TIL, imlo va BMB 30 talik test (Reyting tizimi bilan)\n"
        "🔬 **Ilmiy izlanuvchilar uchun:** OAK maqola va tezis loyihalash\n\n"
        "👇 *Yo'nalishingizga mos bo'limni tanlang:* \n"
        "╰─────────────────────────────────────╯"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data in ["check_sub", "refresh_menu"])
def callback_handler(call):
    save_user(call.from_user)
    if call.data == "check_sub":
        if is_subscribed(call.from_user.id):
            bot.answer_callback_query(call.id, "🎉 Obuna tasdiqlandi!")
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            send_welcome(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)
    elif call.data == "refresh_menu":
        bot.answer_callback_query(call.id, "Asosiy menyu faollashdi")
        send_welcome(call.message)

# --- MATN KIRITISH BOSQICHI ---
def process_custom_step(message, prompt_template):
    user_input = message.text.strip()
    if user_input == "🔙 Asosiy menyu":
        send_welcome(message)
        return

    if check_security_violation(user_input):
        bot.reply_to(message, SECURITY_WARNING, parse_mode="Markdown")
        return

    bot.reply_to(message, "⚡️ *Filologik tahlil jarayoni boshlandi, iltimos kuting...*", parse_mode="Markdown")
    try:
        final_prompt = prompt_template.format(input=user_input)
        result = generate_ai_content(final_prompt, chat_id=message.chat.id)
        deliver_response(message.from_user.id, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")

# --- ASOSIY ISHLOVCHI ---
@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    save_user(message.from_user)

    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = message.text

    if text == "🔙 Asosiy menyu":
        bot.send_message(message.chat.id, "📋 Asosiy toifalardan birini tanlang:", reply_markup=get_main_menu(message.from_user.id))
        return

    elif text == "📊 Boshqaruv & Statistika" and int(message.from_user.id) == int(ADMIN_ID):
        show_admin_stats(message.chat.id)
        return

    # 1. GURUH TANLOVLARI
    elif text == "🎓 Talabalar uchun":
        bot.send_message(message.chat.id, "🎓 **Talabalar uchun maxsus filologik bo'limlar:**", reply_markup=get_group_menu("talaba"))

    elif text == "👨‍🏫 O'qituvchilar uchun":
        bot.send_message(message.chat.id, "👨‍🏫 **O'qituvchilar va metodistlar uchun bo'lim:**", reply_markup=get_group_menu("oqituvchi"))

    elif text == "🎒 Abituriyentlar uchun":
        bot.send_message(message.chat.id, "🎒 **Abituriyentlar va Milliy sertifikatga tayyorgarlik bo'limi:**", reply_markup=get_group_menu("abituriyent"))

    elif text == "🔬 Ilmiy izlanuvchilar uchun":
        bot.send_message(message.chat.id, "🔬 **Doktorant va mustaqil izlanuvchilar bo'limi:**", reply_markup=get_group_menu("izlanuvchi"))

    # 2. TALABALAR UCHUN BO'LIMLAR
    elif text == "📜 G'azal tahlili":
        bot.send_message(message.chat.id, "📜 **G'azal va mumtoz baytlar sharhi:**", reply_markup=get_sub_menu("gazal"))

    elif text == "✍️ Baytni yuborish":
        msg = bot.reply_to(message, "✍️ Badiiy tahlil qilmoqchi bo'lgan baytingizni yuboring:")
        p = "Ushbu mumtoz baytni badiiy tahlil qiling: '{input}'. San'atlari, falsafiy ma'nosi va so'zlar sharhini bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy mumtoz bayt":
        bot.reply_to(message, "⏳ *Mumtoz adabiyotimizdan nodir bayt olinmoqda...*", parse_mode="Markdown")
        p = "Alisher Navoiy yoki Bobur ijodidan 1-2 bayt keltirib, uning badiiy san'atlari va falsafiy teranligini sharhlang."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    elif text == "📐 Aruz vazni hisoblagich":
        bot.send_message(message.chat.id, "📐 **Aruz tizimi, hijolar va bahrlar tahlili:**", reply_markup=get_sub_menu("aruz"))

    elif text == "✍️ Bayt kiritish":
        msg = bot.reply_to(message, "✍️ Aruzini aniqlamoqchi bo'lgan baytni yuboring:")
        p = (
            "Ushbu baytni aruz tizimi bo'yicha to'liq tahlil qiling:\n'{input}'\n"
            "1. Bo'g'inlar turi (ochiq, yopiq, cho'ziq);\n2. Ruknlar va taf'ilalar;\n3. Vazn va bahr nomi."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Namunaviy aruz tahlili":
        bot.reply_to(message, "⏳ *Aruz bahriga oid mukammal tahlil olinmoqda...*", parse_mode="Markdown")
        p = "Mumtoz adabiyotdan mashhur bir baytni olib, uning ruknlari, hijolari va vaznini mukammal tahlil qilib bering."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    elif text == "🏛 Qadimgi turkiy til":
        bot.send_message(message.chat.id, "🏛 **Qadimgi va eski turkiy til leksikasi:**", reply_markup=get_sub_menu("qadim"))

    elif text == "✍️ Tarixiy so'zni kiritish":
        msg = bot.reply_to(message, "✍️ Ma'nosini bilmoqchi bo'lgan tarixiy yoki arxaik so'zni yozing:")
        p = "'{input}' so'zini qadimgi turkiy manbalar (Devonu lug'atit turk, Boburnoma va Navoiy asarlari) asosida filologik tahlil qiling."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy qadimgi so'z":
        bot.reply_to(message, "⏳ *Qadimgi turkiy manbalardan nodir so'z tanlanmoqda...*", parse_mode="Markdown")
        p = "Qadimgi turkiy tilga oid 1 ta nodir so'zni tanlab, uning etimologiyasi, tarixiy ma'nosi va hozirgi kundagi ekvivalentini yozing."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    elif text == "🔍 So'z etimologiyasi":
        bot.send_message(message.chat.id, "🔍 **Shavkat Rahmatullayev etimologik lug'ati:**", reply_markup=get_sub_menu("etimologiya"))

    elif text == "🎲 Tasodifiy etimologiya":
        bot.reply_to(message, "⏳ *Qiziqarli so'z etimologiyasi tadqiq qilinmoqda...*", parse_mode="Markdown")
        p = "O'zbek tilidagi qiziqarli bir so'zning tarixiy kelib chiqishi, o'zagi va ma'no taraqqiyotini etimologik jihatdan tushuntirib bering."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    # 3. O'QITUVCHILAR UCHUN BO'LIMLAR
    elif text == "📋 Dars ishlanmasi":
        bot.send_message(message.chat.id, "📋 **45 daqiqalik dars ishlanmasi (Konspekt):**", reply_markup=get_sub_menu("konspekt"))

    elif text == "✍️ Mavzuni kiritaman" and message.reply_to_message is None:
        msg = bot.reply_to(message, "📋 Sinf va dars mavzusini yozing (Masalan: *«9-sinf. Ergashgan qo'shma gaplar tahlili»*):")
        p = (
            "Umumta'lim maktabi uchun '{input}' mavzusida to'liq 45 daqiqalik dars ishlanmasi (konspekt) tuzing:\n"
            "1. Dars maqsadi va DTS talablari;\n"
            "2. Dars jihozi va usullari;\n"
            "3. Dars bosqichlari (Vaqt taqsimoti, yangi mavzu, mustahkamlash, baholash va uyga vazifa)."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Namunaviy dars ishlanmasi":
        bot.reply_to(message, "⏳ *Namunaviy konspekt tayyorlanmoqda...*", parse_mode="Markdown")
        p = "Ona tili yoki adabiyot fanidan tasodifiy bir murakkab mavzuga 45 daqiqalik mukammal dars konspektini tuzing."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    elif text == "🎯 Interfaol metodlar":
        bot.send_message(message.chat.id, "🎯 **Zamonaviy pedagogik texnologiyalar:**", reply_markup=get_sub_menu("metod"))

    elif text == "🎲 Tasodifiy metod":
        bot.reply_to(message, "⏳ *Interfaol metod shakllantirilmoqda...*", parse_mode="Markdown")
        p = "Ona tili yoki adabiyot darslari uchun zamonaviy interfaol metod ishlab chiqing: Metod nomi, Maqsadi, Bosqichlari va Topshiriq namunasi."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    # 4. ABITURIYENTLAR UCHUN BO'LIMLAR
    elif text == "📝 Esse tekshiruvi (50 ball)":
        bot.send_message(message.chat.id, "📝 **BMB / Milliy sertifikat Esse tekshiruvi (50 ball):**", reply_markup=get_sub_menu("esse"))

    elif text == "✍️ Esseni yuborish":
        msg = bot.reply_to(
            message,
            "📝 Esse mavzusi va matnini to'liq yuboring:\n"
            "Bot uni 50 ballik mezon asosida tahlil qilib, xatolarni ko'rsatadi."
        )
        p = (
            "Ushbu esse matnini BMB (DTM) ning 50 ballik mezonlari bo'yicha tekshiring:\n'{input}'\n\n"
            "Baholash mezonlari: Mavzuni ochish (15 ball), Dalillar (10 ball), Mantiq (10 ball), Savodxonlik (15 ball). "
            "Jami ball va metodik kamchiliklar sharhini taqdim eting."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Namunaviy esse tahlili":
        bot.reply_to(message, "⏳ *Namunaviy esse tahlili tayyorlanmoqda...*", parse_mode="Markdown")
        p = "Milliy sertifikat darajasidagi namunaviy esse mavzusini oling, unga mos matn keltiring va 50 ballik mezon asosida to'liq tahlil qiling."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    elif text == "📖 So'z izohi (O'TIL)":
        bot.send_message(message.chat.id, "📖 **O'zbek tilining izohli lug'ati (O'TIL):**", reply_markup=get_sub_menu("izoh"))

    elif text == "🔤 Imlo va orfoepiya":
        bot.send_message(message.chat.id, "🔤 **Rasmiy imlo va orfoepiya mezonlari:**", reply_markup=get_sub_menu("imlo"))

    elif text == "✍️ So'z/jumlani kiritish":
        msg = bot.reply_to(message, "✍️ Tekshirmoqchi bo'lgan so'zingiz yoki jumlani yozing:")
        p = "'{input}' bo'yicha amaldagi rasmiy imlo qoidalari va urg'u o'rnini tushuntirib bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Ko'p adashiladigan so'z":
        bot.reply_to(message, "⏳ *Imlo jihatdan murakkab so'z tahlil qilinmoqda...*", parse_mode="Markdown")
        p = "Yozuvda ko'p xato qilinadigan 1 ta murakkab so'zni olib, uning to'g'ri yozilishi va qoidasini yoriting."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    # --- BMB 30 TALIK TEST VA REYTING TIZIMI ---
    elif text == "🧠 BMB 30 talik Test":
        bot.send_message(
            message.chat.id,
            "🧠 **BMB (DTM) standarti bo'yicha 30 talik Onlayn Test sinovi:**\n\n"
            "> Test yakunida nechta to'g'ri ishlaganingiz, sarflangan vaqt va barcha ishtirokchilar orasidagi **egallagan o'rningiz** hisoblab beriladi!\n\n"
            "Tanlang:",
            parse_mode="Markdown",
            reply_markup=get_sub_menu("bmb_test")
        )

    elif text == "🚀 30 talik testni boshlash":
        bot.send_message(
            message.chat.id,
            "⏳ *BMB standarti bo'yicha 30 talik individual test paketi shakllanmoqda...*\n"
            "*(Barcha darsliklar qamrab olinishi uchun 10-15 soniya kuting)*",
            parse_mode="Markdown"
        )
        try:
            questions = generate_30_quiz_questions(message.chat.id)
            user_name = message.from_user.first_name or "Ishtirokchi"
            USER_QUIZ_SESSIONS[message.chat.id] = {
                "name": user_name,
                "questions": questions,
                "current_index": 0,
                "correct_count": 0,
                "start_time": time.time()
            }
            bot.send_message(message.chat.id, "🎯 **Test boshlandi! Omad tilaymiz!**\nHar bir savolga javob belgilashingiz bilan keyingi savol chiqadi:")
            send_next_quiz_poll(message.chat.id)
        except Exception as e:
            bot.reply_to(message, f"❌ Testni boshlashda xatolik yuz berdi: {e}")

    elif text == "🏆 Reyting jadvali":
        show_leaderboard(message.chat.id)

    # 5. ILMIY IZLANUVCHILAR UCHUN BO'LIMLAR
    elif text == "📑 Ilmiy maqola (OAK)":
        bot.send_message(message.chat.id, "📑 **OAK talabidagi Ilmiy maqola konstruktori:**", reply_markup=get_sub_menu("maqola"))

    elif text == "✍️ Mavzuni kiritish":
        msg = bot.reply_to(message, "✍️ Ilmiy tadqiqot mavzusini kiriting (Masalan: *«Boburnoma asarida fitonimlar lingvomadaniyati»*):")
        p = (
            "O'zbekiston Respublikasi OAK talablari va xalqaro IMRAD standarti asosida '{input}' mavzusida ilmiy maqola yozish uchun METODIK KO'RSATMA VA ILMIY REJA loyihasini ishlab chiqing.\n\n"
            "QAT'IY TALAB: Tayyor maqola matnini aslo yozmang! Faqat muallif mustaqil yozishi uchun quyidagi tuzilishda yo'riqnoma bering:\n"
            "1. Tavsiya etiladigan ilmiy reja (IMRAD: Kirish, Metodlar, Natijalar, Xulosa);\n"
            "2. Tadqiqotning ilmiy apparati (dolzarbligi, obyekti, predmeti, maqsadi va vazifalari);\n"
            "3. Annotatsiya va kalit so'zlarni shakllantirish qoidalari;\n"
            "4. Tahlil qismida qaysi lingvistik metodlardan foydalanish tavsiyalari;\n"
            "5. OAK standarti bo'yicha tavsiya etiladigan adabiyotlar yo'nalishi."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy mavzu rejasi":
        bot.reply_to(message, "⏳ *Dolzarb filologik mavzu tanlanmoqda...*", parse_mode="Markdown")
        p = (
            "O'zbek tilshunosligi bo'yicha dolzarb bir mavzuni tanlang. "
            "Ushbu mavzuda OAK talablariga mos ilmiy maqola yozish uchun: puxta ilmiy reja, ilmiy apparat va metodik yo'riqnomani taqdim eting. "
            "Tayyor maqola matnini yozmang, faqat reja va yo'riqnoma bering."
        )
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    elif text == "📄 Ilmiy tezis (Konferensiya)":
        bot.send_message(message.chat.id, "📄 **Konferensiya tezislari bo'limi:**", reply_markup=get_sub_menu("tezis"))

    elif text == "✍️ Tezis mavzusini kiritish":
        msg = bot.reply_to(message, "✍️ Tezis mavzusi yoki asosiy ilmiy g'oyani kiriting:")
        p = (
            "Xalqaro va Respublika konferensiyalari talabi asosida '{input}' mavzusida tezis yozish bo'yicha METODIK KO'RSATMA VA REJA tayyorlang.\n\n"
            "QAT'IY TALAB: Tayyor tezis matnini yozmang! Faqat muallif uchun yo'riqnoma bering:\n"
            "1. Tezisning ixcham va mantiqiy rejasi;\n"
            "2. Dolzarblikni 2-3 jumlada ifodalash qoidasi;\n"
            "3. Asosiy ilmiy yangilik va xulosani shakllantirish tartibi."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy tezis rejasi":
        bot.reply_to(message, "⏳ *Konferensiya uchun mavzu shakllantirilmoqda...*", parse_mode="Markdown")
        p = (
            "Zamonaviy tilshunoslik bo'yicha yangi ilmiy muammoni tanlang. "
            "Konferensiya talablariga mos tezis yozish uchun reja va yozish yo'riqnomasini bering. Tayyor matn bermang."
        )
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    # UMUMIY SO'Z KIRITISH VARIANTLARI
    elif text == "✍️ So'zni kiritish":
        msg = bot.reply_to(message, "✍️ Qaysi so'z tahlili kerak? So'zni yozing:")
        p = "O'zbek tilining izohli lug'ati asosida '{input}' so'zining to'liq ma'nolari va namunaviy gaplarni keltiring."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy O'TIL so'zi":
        bot.reply_to(message, "⏳ *Izohli lug'atdan so'z tanlanmoqda...*", parse_mode="Markdown")
        p = "O'TIL lug'atidan boy ma'noli 1 ta so'zni tanlab, uning to'liq izohini berib o'ting."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    else:
        bot.send_message(message.chat.id, "Iltimos, pastdagi menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu(message.from_user.id))

print("AI Tilshunos v8.0 (30-Quiz Leaderboard Edition) faol ishga tushdi...")
bot.infinity_polling()

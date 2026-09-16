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

# --- RENDER WEB SERVICE PORTI ---
app = Flask(__name__)

@app.route('/')
def home():
    return "AI Tilshunos & Metodist v10.2 (Selective Route Quiz Edition) Faol!"

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

USERS_FILE = "users.json"
RESULTS_FILE = "test_results.json"

ACTIVE_QUIZ_TRACKER = {}
POLL_CORRECT_MAP = {}
READY_MATCHES = {}
ADMIN_POST_STORAGE = {}
PENDING_QUIZZES = {}

IMZO = (
    "\n\n╭───────────────────────╮\n"
    f"  🏛 **Rasmiy kanal:** {CHANNEL_USERNAME}\n"
    "  ✨ **AI Asistent:** @aitilshunosbot\n"
    "╰───────────────────────╯"
)

# --- TARIXIY DAVRLAR RO'YXATI ---
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

# --- QAT'IY XAVFSIZLIK VA MAZMUN FILTRI ---
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

# --- MA'LUMOTLARNI SAQLASH ---
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
        markup.row(
            tele_types.KeyboardButton("☀️ Kun hikmati (Admin)"),
            tele_types.KeyboardButton("⚡️ Motivatsiya (Admin)")
        )
        markup.row(tele_types.KeyboardButton("📊 Boshqaruv & Statistika"))
    return markup

def get_group_menu(group_name):
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if group_name == "talaba":
        markup.row(tele_types.KeyboardButton("📜 G'azal tahlili"), tele_types.KeyboardButton("📐 Aruz vazni hisoblagich"))
        markup.row(tele_types.KeyboardButton("🏛 Qadimgi turkiy til"), tele_types.KeyboardButton("🔍 So'z etimologiyasi"))
    elif group_name == "oqituvchi":
        markup.row(tele_types.KeyboardButton("📋 Dars ishlanmasi"), tele_types.KeyboardButton("🎯 Interfaol metodlar"))
        markup.row(tele_types.KeyboardButton("📝 Attestatsiya Testi (40 ta Y1, Y2, Y3)"))
    elif group_name == "abituriyent":
        markup.row(tele_types.KeyboardButton("📝 Esse tekshiruvi (50 ball)"), tele_types.KeyboardButton("📖 So'z izohi (O'TIL)"))
        markup.row(tele_types.KeyboardButton("🔤 Imlo va orfoepiya"), tele_types.KeyboardButton("🧠 BMB 30 talik Test"))
        markup.row(tele_types.KeyboardButton("📚 Mavzulashtirilgan BMB Test (30 ta)"))
    elif group_name == "izlanuvchi":
        markup.row(tele_types.KeyboardButton("📑 Ilmiy maqola (OAK)"), tele_types.KeyboardButton("📄 Ilmiy tezis (Konferensiya)"))
    
    markup.row(tele_types.KeyboardButton("🔙 Asosiy menyu"))
    return markup

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

# --- NATIJALARNI ADMINGA TASDIQLASH BILAN YO'NALTIRISH ---
def deliver_response(user_id, text):
    if len(text) > 3900:
        text = text[:3900] + "..."

    is_admin = False
    try:
        if int(user_id) == int(ADMIN_ID):
            is_admin = True
    except Exception:
        pass

    if is_admin:
        post_id = f"post_{int(time.time())}_{random.randint(100, 999)}"
        ADMIN_POST_STORAGE[post_id] = text

        markup = tele_types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            tele_types.InlineKeyboardButton(text="📢 Kanalga yuborish", callback_data=f"send_chan_{post_id}"),
            tele_types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{post_id}")
        )
        bot.send_message(
            user_id,
            f"{text}\n\n━━━━━━━━━━━━━━━━━━━━\n👑 **Admin:** Ushbu materialni kanalga e'lon qilasizmi?",
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        bot.send_message(user_id, text, parse_mode="Markdown")

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

# --- QUIZ TEST GENERATORLARI ---
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

    ACTIVE_QUIZ_TRACKER[target_chat_id] = {
        "scores": {},
        "total_q": total_q
    }

    bot.send_message(
        target_chat_id,
        f"🏁 **DIQQAT, {title.upper()} BOSHLANDI!**\n\n"
        f"▫️ Jami savollar: **{total_q} ta**\n"
        f"▫️ Har bir savolga ajratilgan vaqt: **⏳ {duration_per_q} soniya**\n"
        f"▫️ Rasmiy kanal: {CHANNEL_USERNAME}\n\n"
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
    if is_channel:
        finish_msg = (
            f"╔════════════════════════════════╗\n"
            f"  🏆 **{title.upper()} YAKUNLANDI!**\n"
            f"╚════════════════════════════════╝\n\n"
            "Kanalda o'tkazilgan test muvaffaqiyatli yakunlandi.\n"
            "💡 *Telegram qoidasiga ko'ra kanallardagi ovoz berish anonim bo'ladi. "
            "Individual reyting va o'rningizni bilish uchun testni botda yoki o'z guruhingizda ishlang!*\n\n"
            f"Rasmiy manba: {CHANNEL_USERNAME}"
        )
    else:
        scores = tracker["scores"] if tracker else {}
        if scores:
            sorted_participants = sorted(scores.items(), key=lambda x: x[1]["correct"], reverse=True)
            leaderboard_text = ""
            for rank, (uid, info) in enumerate(sorted_participants, 1):
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"`#{rank}`"
                perc = round((info["correct"] / total_q) * 100, 1)
                leaderboard_text += f"{medal} **{info['name']}** — `{info['correct']}/{total_q}` to'g'ri ({perc}%)\n"

            finish_msg = (
                f"╔════════════════════════════════╗\n"
                f"  🏆 **{title.upper()} REYTINGI**\n"
                f"╚════════════════════════════════╝\n\n"
                f"👥 Jami ishtirokchilar: **{len(sorted_participants)} nafar**\n"
                f"📊 Savollar soni: **{total_q} ta**\n\n"
                "🏅 **ISHTIROKCHILARNING EGALLAGAN O'RINLARI:**\n"
                f"{leaderboard_text}\n"
                "────────────────────────────────\n"
                f"✨ Rasmiy filologik kanalimiz: {CHANNEL_USERNAME}"
            )
        else:
            finish_msg = (
                f"╔════════════════════════════════╗\n"
                f"  🏆 **{title.upper()} YAKUNLANDI!**\n"
                f"╚════════════════════════════════╝\n\n"
                "Test yakunlandi. Hech bir ishtirokchi javob belgilamadi.\n\n"
                f"Rasmiy kanal: {CHANNEL_USERNAME}"
            )

    bot.send_message(target_chat_id, finish_msg, parse_mode="Markdown")

# --- 3 KISHI «TAYYORMAN» TIZIMI (Guruh va Kanal uchun) ---
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
        f"▫️ Savollar soni: **{len(questions)} ta**\n"
        f"▫️ Vaqt me'yori: Har bir savolga **⏳ {duration_per_q} soniya**\n"
        f"▫️ Manzil: {CHANNEL_USERNAME}\n\n"
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

# --- TEST TAYYOR BO'LGANDA TANLOV MENYUSINI CHIQARISH ---
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
        # BOTDA ISHLASH TANLANGANDA DARHOL BOSHLANADI (KUTISHLARSIZ)
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
            f"Rasmiy kanal: {CHANNEL_USERNAME}\n"
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
            questions = get_themed_bmb_questions("5-11-sinf barcha darsliklari")
            setup_match_lobby(message.chat.id, questions, duration_per_q=30, title="Guruh Bellashuvi (BMB 30 ta)")
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
            "Qat'iy format (faqat shu ko'rinishda bering):\n"
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
            "Qat'iy format (faqat shu ko'rinishda bering):\n"
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
    channel_post = f"{clean_text}\n\n───────────────\n🌟 **Rasmiy kanal:** {CHANNEL_USERNAME}"

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
        "🏛 **AI TILSHUNOS & METODIST (v10.2)** portaliga xush kelibsiz!\n\n"
        "Quyidagi maqsadli toifalardan birini tanlang:\n\n"
        "🎓 **Talabalar uchun:** Mumtoz meros, aruz, qadimgi til va etimologiya\n"
        "👨‍🏫 **O'qituvchilar uchun:** Konspektlar, metodlar va 40 talik Attestatsiya testi\n"
        "🎒 **Abituriyentlar uchun:** 50 ballik esse, O'TIL, imlo, BMB 30 talik va Mavzuli testlar\n"
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

# --- ASOSIY MENYU VA XABARLAR ISHLOVCHISI ---
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

    # Faqat adminga ko'rinadigan bo'limlar
    elif text == "📊 Boshqaruv & Statistika" and is_admin:
        users = load_data(USERS_FILE)
        ch_count = bot.get_chat_member_count(CHANNEL_USERNAME)
        bot.send_message(
            message.chat.id,
            f"📊 **Boshqaruv Paneli (Admin):**\n\n"
            f"▫️ Jami bot a'zolari: `{len(users)} nafar`\n"
            f"▫️ Rasmiy kanal obunachilari: `{ch_count} nafar`\n"
            f"▫️ Xabar tarqatish: `/send matn`",
            parse_mode="Markdown"
        )
        return

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
        return

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
        return

    # 1. GURUHLAR
    elif text == "🎓 Talabalar uchun":
        bot.send_message(message.chat.id, "🎓 **Talabalar uchun filologik bo'limlar:**", reply_markup=get_group_menu("talaba"))

    elif text == "👨‍🏫 O'qituvchilar uchun":
        bot.send_message(message.chat.id, "👨‍🏫 **O'qituvchilar va metodistlar bo'limi:**", reply_markup=get_group_menu("oqituvchi"))

    elif text == "🎒 Abituriyentlar uchun":
        bot.send_message(message.chat.id, "🎒 **Abituriyentlar va sertifikat bo'limi:**", reply_markup=get_group_menu("abituriyent"))

    elif text == "🔬 Ilmiy izlanuvchilar uchun":
        bot.send_message(message.chat.id, "🔬 **Ilmiy izlanuvchilar bo'limi:**", reply_markup=get_group_menu("izlanuvchi"))

    # 2. O'QITUVCHILAR — ATTESTATSIYA TESTI (40 TA Y1, Y2, Y3)
    elif text == "📝 Attestatsiya Testi (40 ta Y1, Y2, Y3)":
        bot.send_message(
            message.chat.id,
            "⏳ *O'qituvchilar attestatsiyasi spetsifikatsiyasi bo'yicha 40 ta Y1, Y2, Y3 testlari shakllantirilmoqda...*\n"
            "*(Biroz kuting, savollar takrorsiz va darsliklar asosida tuzilmoqda)*",
            parse_mode="Markdown"
        )
        try:
            questions = get_attestation_questions()
            offer_quiz_dispatch(message.chat.id, u_id, questions, duration_per_q=40, title="Pedagoglar Attestatsiya Testi (40 ta)")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xatolik: {e}")

    # 3. ABITURIYENTLAR — MAVZULASHTIRILGAN TEST (30 TA, 30s)
    elif text == "📚 Mavzulashtirilgan BMB Test (30 ta)":
        msg = bot.reply_to(
            message,
            "📚 **Mavzulashtirilgan BMB Test:**\n\n"
            "Qaysi darslik mavzusi bo'yicha 30 talik test tuzmoqchisiz?\n"
            "👉 Masalan: *«Fe'l nisbatlari»*, *«Ergashgan qo'shma gaplar»*, *«Boburnoma tahlili»* yoki *«Fonetik hodisalar»*\n\n"
            "Mavzuni yozib yuboring:"
        )
        def start_themed_quiz(msg_obj):
            theme = msg_obj.text.strip()
            if theme == "🔙 Asosiy menyu":
                send_welcome(msg_obj)
                return
            bot.send_message(msg_obj.chat.id, f"⏳ *«{theme}» mavzusi bo'yicha 30 talik test shakllanmoqda... Har bir savolga ⏳ 30 soniya!*", parse_mode="Markdown")
            try:
                questions = get_themed_bmb_questions(theme)
                offer_quiz_dispatch(msg_obj.chat.id, msg_obj.from_user.id, questions, duration_per_q=30, title=f"BMB Mavzuli Test: {theme}")
            except Exception as e:
                bot.send_message(msg_obj.chat.id, f"❌ Xatolik: {e}")

        bot.register_next_step_handler(msg, start_themed_quiz)

    # 4. STANDART BMB 30 TALIK TEST
    elif text == "🧠 BMB 30 talik Test":
        bot.send_message(
            message.chat.id,
            "⏳ *BMB standarti bo'yicha 30 talik to'liq test shakllanmoqda...*",
            parse_mode="Markdown"
        )
        try:
            questions = get_themed_bmb_questions("5-11-sinf barcha bo'limlari")
            offer_quiz_dispatch(message.chat.id, u_id, questions, duration_per_q=30, title="BMB Umumiy Test (30 ta)")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xatolik: {e}")

    # 5. BOSHQA BARCHA ILMIY-METODIK BUYRUQLAR
    elif text == "📋 Dars ishlanmasi":
        msg = bot.reply_to(message, "📋 Qaysi sinf va mavzu bo'yicha dars ishlanmasi kerak? Yozib yuboring:")
        p = "Umumta'lim maktabi uchun '{input}' mavzusida to'liq 45 daqiqalik dars ishlanmasi (konspekt) tuzing."
        def process_step(m):
            bot.send_message(m.chat.id, "⏳ Tayyorlanmoqda...")
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "📝 Esse tekshiruvi (50 ball)":
        msg = bot.reply_to(message, "📝 Esse mavzusi va matnini to'liq yuboring:")
        p = "Ushbu esse matnini BMB 50 ballik mezoni bo'yicha tekshiring: '{input}'"
        def process_step(m):
            bot.send_message(m.chat.id, "⏳ Tekshirilmoqda...")
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "📜 G'azal tahlili":
        msg = bot.reply_to(message, "✍️ Tahlil qilmoqchi bo'lgan baytingizni yuboring:")
        p = "Ushbu baytni badiiy tahlil qiling: '{input}'. San'atlari va so'zlar sharhini bering."
        def process_step(m):
            bot.send_message(m.chat.id, "⏳ Tahlil qilinmoqda...")
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "📐 Aruz vazni hisoblagich":
        msg = bot.reply_to(message, "✍️ Aruzini aniqlamoqchi bo'lgan baytni yuboring:")
        p = "Ushbu baytni aruz tizimi bo'yicha tahlil qiling (hijolar, ruknlar, bahr nomi): '{input}'"
        def process_step(m):
            bot.send_message(m.chat.id, "⏳ Aniqlanmoqda...")
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "🏛 Qadimgi turkiy til":
        msg = bot.reply_to(message, "✍️ Qaysi tarixiy yoki arxaik so'z kerak? Yozing:")
        p = "'{input}' so'zini qadimgi turkiy manbalar asosida filologik tahlil qiling."
        def process_step(m):
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "🔍 So'z etimologiyasi":
        msg = bot.reply_to(message, "🔍 Etimologiyasini bilmoqchi bo'lgan so'zingizni yozing:")
        p = "'{input}' so'zining tarixiy ildizi va etimologiyasini tushuntiring."
        def process_step(m):
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "📖 So'z izohi (O'TIL)":
        msg = bot.reply_to(message, "📖 Izohini bilmoqchi bo'lgan so'zingizni yozing:")
        p = "O'zbek tilining izohli lug'ati asosida '{input}' so'zini to'liq sharhlang."
        def process_step(m):
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "🔤 Imlo va orfoepiya":
        msg = bot.reply_to(message, "✍️ Tekshirmoqchi bo'lgan so'z yoki jumlani yozing:")
        p = "'{input}' bo'yicha rasmiy imlo qoidalari va urg'uni tushuntiring."
        def process_step(m):
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "🎯 Interfaol metodlar":
        msg = bot.reply_to(message, "🎯 Qaysi mavzu uchun metod kerak? Yozing:")
        p = "'{input}' mavzusi uchun zamonaviy interfaol metod ishlab chiqing."
        def process_step(m):
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "📑 Ilmiy maqola (OAK)":
        msg = bot.reply_to(message, "✍️ Maqola mavzusini kiriting:")
        p = "OAK talablari asosida '{input}' mavzusida maqola yozish uchun REJA va METODIK KO'RSATMA bering. Tayyor matn bermang."
        def process_step(m):
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    elif text == "📄 Ilmiy tezis (Konferensiya)":
        msg = bot.reply_to(message, "✍️ Tezis mavzusini kiriting:")
        p = "Konferensiya uchun '{input}' mavzusida tezis yozish bo'yicha REJA va YO'RIQNOMA bering. Tayyor matn bermang."
        def process_step(m):
            deliver_response(m.from_user.id, generate_ai_content(p.format(input=m.text)))
        bot.register_next_step_handler(msg, process_step)

    else:
        bot.send_message(message.chat.id, "Iltimos, menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu(u_id))

print("AI Tilshunos v10.2 (Selective Route Quiz) faol ishga tushdi...")
bot.infinity_polling()

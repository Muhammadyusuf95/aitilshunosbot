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
    return "AI Tilshunos & Metodist v9.1 (Channel Poll Fixed) Faol!"

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

READY_MATCHES = {}

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

# --- MENYULAR ---
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
        "imlo": ("✍️ So'z/jumlani kiritish", "🎲 Ko'p adashiladigan so'z")
    }
    btn1, btn2 = labels.get(category, ("✍️ O'zim kiritaman", "🎲 Tasodifiy"))
    markup.row(tele_types.KeyboardButton(btn1), tele_types.KeyboardButton(btn2))
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

# --- 30 TALIK BMB TESTINI GENERATSIYA QILISH ---
def generate_30_quiz_questions(chat_id):
    try:
        bot.send_chat_action(chat_id, 'typing')
    except Exception:
        pass

    random_seed = random.randint(10000, 99999)
    prompt = (
        f"O'zbekiston Respublikasi BMB (DTM) standarti bo'yicha tasdiqlangan 5-11-sinf Ona tili va adabiyoti "
        f"darsliklaridan TO'LIQ 30 TA original Quiz test tuzing (Variant #{random_seed}).\n\n"
        "TAQSIMOT:\n"
        "1-4: Fonetika, orfoepiya, imlo;\n"
        "5-8: Leksikologiya, frazeologiya, paronimlar;\n"
        "9-14: Morfologiya (turkumlar, qo'shimchalar, fe'l shakllari);\n"
        "15-18: Sintaksis va tinish belgilari;\n"
        "19-22: Matn mantiqiy tahlili;\n"
        "23-26: Mumtoz adabiyot (Navoiy, Bobur, aruz, badiiy san'atlar);\n"
        "27-30: Jadid va XX asr o'zbek adabiyoti.\n\n"
        "Faqat JSON formatida (qo'shimcha so'zsiz):\n"
        "[\n"
        "  {\n"
        '    "question": "1-savol matni (maks 250 belgi)",\n'
        '    "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '    "correct_option_id": 0,\n'
        '    "explanation": "Izoh va darslik manbasi (maks 180 belgi)"\n'
        "  }\n"
        "]\n"
        "DIQQAT: Aniq 30 ta savol bo'lsin. Variantlar uzunligi 95 belgidan oshmasin."
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
                if isinstance(questions, list) and len(questions) >= 15:
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

# --- TESTNI 40 SONIYALIK QAT'IY REJIMDA O'TKAZISH LOOP'I (XATOSIZ TUZATILDI) ---
def run_quiz_test_loop(target_chat_id, questions, is_private=False):
    total_q = len(questions)
    
    # Kanalda anonim bo'lishi SHART! Guruh yoki botda esa ochiq bo'lishi mumkin
    is_anon = True if str(target_chat_id).startswith("@") or not is_private else False

    bot.send_message(
        target_chat_id,
        "🏁 **DIQQAT, TEST BOSHLANDI!**\n\n"
        f"▫️ Jami savollar soni: **{total_q} ta**\n"
        "▫️ Har bir savol uchun ajratilgan vaqt: **⏳ 40 soniya**\n"
        f"▫️ Rasmiy manba: {CHANNEL_USERNAME}\n\n"
        "Quyidagi savollarga javob bering:",
        parse_mode="Markdown"
    )
    time.sleep(3)

    for idx, q_data in enumerate(questions, 1):
        question_text = f"[{idx}/{total_q}] ⏳ 40s | {q_data['question']}"
        if len(question_text) > 295:
            question_text = question_text[:292] + "..."

        options = [str(opt)[:95] for opt in q_data["options"][:4]]
        # Kamida 2 ta variant bo'lishi shart
        if len(options) < 2:
            options = ["A varianti", "B varianti"]

        correct_id = int(q_data.get("correct_option_id", 0))
        if correct_id < 0 or correct_id >= len(options):
            correct_id = 0

        explanation = f"{q_data.get('explanation', '')}\n👉 {CHANNEL_USERNAME}"[:195]

        try:
            bot.send_poll(
                chat_id=target_chat_id,
                question=question_text,
                options=options,
                type="quiz",
                correct_option_id=correct_id,
                explanation=explanation,
                is_anonymous=is_anon,
                open_period=40
            )
        except Exception as err:
            print(f"Poll jo'natish xatosi (savol #{idx}): {err}")
            try:
                # Agar open_period yoki boshqa parametr bilan xato bersa, oddiy poll ko'rinishida yuborish
                bot.send_poll(
                    chat_id=target_chat_id,
                    question=question_text,
                    options=options,
                    type="quiz",
                    correct_option_id=correct_id,
                    is_anonymous=True
                )
            except Exception as e2:
                print(f"Qayta urinishda ham xato: {e2}")

        time.sleep(42)

    finish_msg = (
        "╔════════════════════════════════╗\n"
        "  🏆 **30 TALIK BMB TESTI YAKUNLANDI!**\n"
        "╚════════════════════════════════╝\n\n"
        f"Barcha ishtirokchilarga tashakkur! Test natijalari qayd etildi.\n\n"
        f"Rasmiy ilmiy kanalimiz: {CHANNEL_USERNAME}"
    )
    bot.send_message(target_chat_id, finish_msg, parse_mode="Markdown")

# --- «TAYYORMAN» TUGMASI BILAN START BERISHNI BOSHQARISH ---
def send_match_announcement(chat_id, questions, match_id, title_prefix=""):
    READY_MATCHES[match_id] = {
        "chat_id": chat_id,
        "questions": questions,
        "ready_users": {},
        "started": False
    }

    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(
            text="✋ Men tayyorman (0/3)", 
            callback_data=f"ready_{match_id}"
        ),
        tele_types.InlineKeyboardButton(
            text="📢 Kanalga a'zo bo'lish", 
            url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        )
    )

    announcement = (
        f"╔════════════════════════════════╗\n"
        f"  🧠 **BMB 30 TALIK TEST SINOVI: {title_prefix}**\n"
        f"╚════════════════════════════════╝\n\n"
        "📚 **5-11-sinf Ona tili va adabiyot darsliklari asosida**\n"
        "⏱ **Vaqt me'yori:** Har bir savolga ⏳ 40 soniyadan\n\n"
        "⚠️ **Qoida:** Test boshlanishi uchun kamida **3 nafar ishtirokchi** "
        "quyidagi «Men tayyorman» tugmasini bosishi lozim!\n\n"
        f"Rasmiy hamkor kanal: {CHANNEL_USERNAME}"
    )
    bot.send_message(chat_id, announcement, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ready_"))
def callback_ready_handler(call):
    match_id = call.data.replace("ready_", "")
    match_data = READY_MATCHES.get(match_id)
    if not match_data:
        bot.answer_callback_query(call.id, "Ushbu test muddati tugagan yoki allaqachon boshlangan.", show_alert=True)
        return

    if match_data["started"]:
        bot.answer_callback_query(call.id, "Test allaqachon start olgan!", show_alert=True)
        return

    u_id = call.from_user.id
    u_name = call.from_user.first_name or "Ishtirokchi"

    if u_id in match_data["ready_users"]:
        bot.answer_callback_query(call.id, "Siz tayyormansiz! Boshqalarni kutyapmiz...", show_alert=False)
        return

    match_data["ready_users"][u_id] = u_name
    count = len(match_data["ready_users"])
    bot.answer_callback_query(call.id, f"Qabul qilindi! ({count}/3)")

    if count < 3:
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(
                text=f"✋ Men tayyorman ({count}/3)", 
                callback_data=f"ready_{match_id}"
            ),
            tele_types.InlineKeyboardButton(
                text="📢 Kanalga a'zo bo'lish", 
                url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
            )
        )
        try:
            bot.edit_message_reply_markup(chat_id=match_data["chat_id"], message_id=call.message.message_id, reply_markup=markup)
        except Exception:
            pass
    else:
        # Kamida 3 nafar bo'ldi -> Start beriladi
        match_data["started"] = True
        names = ", ".join(list(match_data["ready_users"].values())[:5])
        try:
            bot.edit_message_text(
                chat_id=match_data["chat_id"],
                message_id=call.message.message_id,
                text=f"🎉 **Yetarli ishtirokchilar yig'ildi! (Tayyorlar: {names})**\n\n🚀 Test 5 soniyadan so'ng boshlanadi...",
                parse_mode="Markdown"
            )
        except Exception:
            pass

        time.sleep(5)
        threading.Thread(
            target=run_quiz_test_loop, 
            args=(match_data["chat_id"], match_data["questions"], False), 
            daemon=True
        ).start()

# --- ADMIN STATISTIKASI ---
def show_admin_stats(chat_id):
    users = load_data(USERS_FILE)
    total_users = len(users)

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
        f"▫️ **Kanal auditoriyasi:** `{channel_members}` obunachi\n\n"
        "👥 **Oxirgi faol a'zolar:**\n"
        f"{last_users_text}\n"
        "📢 *Barcha a'zolarga xabar yuborish:* `/send xabar matni`\n"
        "╰──────────────────────────────────────────╯"
    )
    bot.send_message(chat_id, msg, parse_mode="Markdown")

# --- GURUHDAN /quiz_start BUYRUG'I ---
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
            questions = generate_30_quiz_questions(message.chat.id)
            match_id = f"grp_{message.chat.id}_{int(time.time())}"
            send_match_announcement(message.chat.id, questions, match_id, title_prefix="GURUH BELLASHUVI")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")
    else:
        bot.reply_to(message, "Ushbu buyruq faqat Telegram guruhlarida ishlaydi.")

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
        "🏛 **AI TILSHUNOS & METODIST (v9.1)** portaliga xush kelibsiz!\n\n"
        "Quyidagi asosiy toifalardan birini tanlang:\n\n"
        "🎓 **Talabalar uchun:** G'azal, aruz, qadimgi til va etimologiya\n"
        "👨‍🏫 **O'qituvchilar uchun:** Dars ishlanmalari va zamonaviy metodlar\n"
        "🎒 **Abituriyentlar uchun:** 50 ballik esse, O'TIL, imlo va BMB 30 talik test\n"
        "🔬 **Ilmiy izlanuvchilar uchun:** OAK maqola va tezis loyihalash\n\n"
        "👇 *Yo'nalishingizni tanlang:* \n"
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

# --- MATNLI BOSQICHLARNI QAYTA ISHLASH ---
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
        if len(result) > 3900:
            result = result[:3900] + "..."
        bot.send_message(message.chat.id, result, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")

# --- ASOSIY MENYU VA XABARLAR ISHLOVCHISI ---
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

    # 1. GURUHLAR
    elif text == "🎓 Talabalar uchun":
        bot.send_message(message.chat.id, "🎓 **Talabalar uchun maxsus bo'limlar:**", reply_markup=get_group_menu("talaba"))

    elif text == "👨‍🏫 O'qituvchilar uchun":
        bot.send_message(message.chat.id, "👨‍🏫 **O'qituvchilar va metodistlar bo'limi:**", reply_markup=get_group_menu("oqituvchi"))

    elif text == "🎒 Abituriyentlar uchun":
        bot.send_message(message.chat.id, "🎒 **Abituriyentlar bo'limi:**", reply_markup=get_group_menu("abituriyent"))

    elif text == "🔬 Ilmiy izlanuvchilar uchun":
        bot.send_message(message.chat.id, "🔬 **Ilmiy izlanuvchilar bo'limi:**", reply_markup=get_group_menu("izlanuvchi"))

    # 2. TALABALAR
    elif text == "📜 G'azal tahlili":
        bot.send_message(message.chat.id, "📜 **G'azal va mumtoz baytlar sharhi:**", reply_markup=get_sub_menu("gazal"))

    elif text == "✍️ Baytni yuborish":
        msg = bot.reply_to(message, "✍️ Badiiy tahlil qilmoqchi bo'lgan baytingizni yuboring:")
        p = "Ushbu mumtoz baytni badiiy tahlil qiling: '{input}'. San'atlari, falsafiy ma'nosi va so'zlar sharhini bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy mumtoz bayt":
        bot.reply_to(message, "⏳ *Mumtoz adabiyotimizdan nodir bayt olinmoqda...*", parse_mode="Markdown")
        p = "Alisher Navoiy yoki Bobur ijodidan 1-2 bayt keltirib, uning badiiy san'atlari va falsafiy teranligini sharhlang."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

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
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

    elif text == "🏛 Qadimgi turkiy til":
        bot.send_message(message.chat.id, "🏛 **Qadimgi va eski turkiy til leksikasi:**", reply_markup=get_sub_menu("qadim"))

    elif text == "✍️ Tarixiy so'zni kiritish":
        msg = bot.reply_to(message, "✍️ Ma'nosini bilmoqchi bo'lgan tarixiy yoki arxaik so'zni yozing:")
        p = "'{input}' so'zini qadimgi turkiy manbalar asosida filologik tahlil qiling."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy qadimgi so'z":
        bot.reply_to(message, "⏳ *Qadimgi turkiy manbalardan nodir so'z tanlanmoqda...*", parse_mode="Markdown")
        p = "Qadimgi turkiy tilga oid 1 ta nodir so'zni tanlab, uning etimologiyasi va ma'nosini yozing."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

    elif text == "🔍 So'z etimologiyasi":
        bot.send_message(message.chat.id, "🔍 **Shavkat Rahmatullayev etimologik lug'ati:**", reply_markup=get_sub_menu("etimologiya"))

    elif text == "🎲 Tasodifiy etimologiya":
        bot.reply_to(message, "⏳ *Qiziqarli so'z etimologiyasi tadqiq qilinmoqda...*", parse_mode="Markdown")
        p = "O'zbek tilidagi qiziqarli bir so'zning tarixiy kelib chiqishi va ma'no taraqqiyotini tushuntirib bering."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

    # 3. O'QITUVCHILAR
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
        p = "Ona tili yoki adabiyot fanidan tasodifiy bir murakkab mavzuga 45 daqiqalik dars konspektini tuzing."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

    elif text == "🎯 Interfaol metodlar":
        bot.send_message(message.chat.id, "🎯 **Zamonaviy pedagogik texnologiyalar:**", reply_markup=get_sub_menu("metod"))

    elif text == "🎲 Tasodifiy metod":
        bot.reply_to(message, "⏳ *Interfaol metod shakllantirilmoqda...*", parse_mode="Markdown")
        p = "Ona tili yoki adabiyot darslari uchun zamonaviy interfaol metod ishlab chiqing: Metod nomi, Maqsadi, Bosqichlari va Topshiriq."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

    # 4. ABITURIYENTLAR
    elif text == "📝 Esse tekshiruvi (50 ball)":
        bot.send_message(message.chat.id, "📝 **BMB / Milliy sertifikat Esse tekshiruvi (50 ball):**", reply_markup=get_sub_menu("esse"))

    elif text == "✍️ Esseni yuborish":
        msg = bot.reply_to(
            message,
            "📝 Esse mavzusi va matnini to'liq yuboring:\n"
            "Bot uni 50 ballik mezon asosida tahlil qilib beradi."
        )
        p = (
            "Ushbu esse matnini BMB (DTM) ning 50 ballik mezonlari bo'yicha tekshiring:\n'{input}'\n\n"
            "Mavzu (15), Dalil (10), Mantiq (10), Savodxonlik (15), Jami ball va tavsiyalar."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Namunaviy esse tahlili":
        bot.reply_to(message, "⏳ *Namunaviy esse tahlili tayyorlanmoqda...*", parse_mode="Markdown")
        p = "Milliy sertifikat darajasidagi 1 ta namunaviy esse matnini keltiring va uni 50 ballik mezon asosida tahlil qiling."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

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
        p = "Yozuvda ko'p xato qilinadigan 1 ta murakkab so'zni olib, uning to'g'ri yozilish qoidasini yoriting."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

    # --- BMB 30 TALIK TEST TIZIMI ---
    elif text == "🧠 BMB 30 talik Test":
        is_admin = (int(message.from_user.id) == int(ADMIN_ID))
        
        if is_admin:
            markup = tele_types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                tele_types.InlineKeyboardButton(text="📢 Kanalga e'lon qilish (@onatilidanyordam)", callback_data="admin_quiz_channel"),
                tele_types.InlineKeyboardButton(text="🤖 Botning o'zida sinab ko'rish", callback_data="user_quiz_bot")
            )
            bot.send_message(
                message.chat.id,
                "👑 **HURMATLI ADMIN:**\n\n"
                "30 talik BMB testini qayerda o'tkazmoqchisiz?",
                reply_markup=markup
            )
        else:
            markup = tele_types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                tele_types.InlineKeyboardButton(text="🤖 Botning o'zida yakkaxon ishlash", callback_data="user_quiz_bot"),
                tele_types.InlineKeyboardButton(text="👥 O'z guruhimga tashlash (Bellashuv)", callback_data="user_quiz_group_info")
            )
            bot.send_message(
                message.chat.id,
                "🧠 **BMB 30 TALIK TEST SINOVI:**\n\n"
                "Qayerda test ishlamoqchisiz? Tanlang:",
                reply_markup=markup
            )

    # 5. ILMIY IZLANUVCHILAR
    elif text == "📑 Ilmiy maqola (OAK)":
        bot.send_message(message.chat.id, "📑 **OAK talabidagi Ilmiy maqola konstruktori:**", reply_markup=get_sub_menu("maqola"))

    elif text == "✍️ Mavzuni kiritish":
        msg = bot.reply_to(message, "✍️ Ilmiy tadqiqot mavzusini kiriting (Masalan: *«Boburnoma asarida fitonimlar lingvomadaniyati»*):")
        p = (
            "O'zbekiston Respublikasi OAK talablari va xalqaro IMRAD standarti asosida '{input}' mavzusida ilmiy maqola yozish uchun METODIK KO'RSATMA VA ILMIY REJA loyihasini ishlab chiqing.\n\n"
            "QAT'IY TALAB: Tayyor maqola matnini aslo yozmang! Faqat muallif mustaqil yozishi uchun reja va yo'riqnoma bering."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy mavzu rejasi":
        bot.reply_to(message, "⏳ *Dolzarb filologik mavzu tanlanmoqda...*", parse_mode="Markdown")
        p = "O'zbek tilshunosligi bo'yicha dolzarb bir mavzuni tanlab, OAK maqolasi uchun reja va ilmiy apparat yo'riqnomasini taqdim eting."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

    elif text == "📄 Ilmiy tezis (Konferensiya)":
        bot.send_message(message.chat.id, "📄 **Konferensiya tezislari bo'limi:**", reply_markup=get_sub_menu("tezis"))

    elif text == "✍️ Tezis mavzusini kiritish":
        msg = bot.reply_to(message, "✍️ Tezis mavzusi yoki asosiy ilmiy g'oyani kiriting:")
        p = "Konferensiya talabi asosida '{input}' mavzusida tezis yozish bo'yicha METODIK KO'RSATMA VA REJA tayyorlang. Tayyor matn bermang."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy tezis rejasi":
        bot.reply_to(message, "⏳ *Konferensiya uchun mavzu shakllantirilmoqda...*", parse_mode="Markdown")
        p = "Zamonaviy tilshunoslik bo'yicha yangi ilmiy muammo tanlab, tezis yozish yo'riqnomasini bering."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

    # UMUMIY SO'Z KIRITISH
    elif text == "✍️ So'zni kiritish":
        msg = bot.reply_to(message, "✍️ Qaysi so'z tahlili kerak? So'zni yozing:")
        p = "O'zbek tilining izohli lug'ati asosida '{input}' so'zining to'liq ma'nolarini keltiring."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy O'TIL so'zi":
        bot.reply_to(message, "⏳ *Izohli lug'atdan so'z tanlanmoqda...*", parse_mode="Markdown")
        p = "O'TIL lug'atidan boy ma'noli 1 ta so'zni tanlab, uning to'liq izohini berib o'ting."
        bot.send_message(message.chat.id, generate_ai_content(p, chat_id=message.chat.id), parse_mode="Markdown")

    else:
        bot.send_message(message.chat.id, "Iltimos, pastdagi menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu(message.from_user.id))

# --- TEST TANLOVLARI CALLBACK HANDLER ---
@bot.callback_query_handler(func=lambda call: call.data in ["admin_quiz_channel", "user_quiz_bot", "user_quiz_group_info"])
def callback_quiz_options(call):
    if call.data == "admin_quiz_channel":
        if int(call.from_user.id) != int(ADMIN_ID):
            bot.answer_callback_query(call.id, "Bu faqat admin uchun!")
            return
        bot.answer_callback_query(call.id, "Kanal uchun test tayyorlanmoqda...")
        bot.send_message(call.message.chat.id, f"⏳ *30 talik test shakllantirilib, {CHANNEL_USERNAME} kanaliga e'lon qilinmoqda...*", parse_mode="Markdown")
        try:
            questions = generate_30_quiz_questions(call.message.chat.id)
            match_id = f"chn_{int(time.time())}"
            send_match_announcement(CHANNEL_USERNAME, questions, match_id, title_prefix="KANAL CHEMPIONATI")
            bot.send_message(call.message.chat.id, f"✅ Test {CHANNEL_USERNAME} kanaliga muvaffaqiyatli joylandi!")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Xatolik yuz berdi: {e}")

    elif call.data == "user_quiz_bot":
        bot.answer_callback_query(call.id, "Individual test boshlanmoqda...")
        bot.send_message(
            call.message.chat.id,
            "⏳ *Siz uchun 30 talik individual test tayyorlanmoqda... Har bir savolga ⏳ 40 soniya vaqt beriladi!*",
            parse_mode="Markdown"
        )
        try:
            questions = generate_30_quiz_questions(call.message.chat.id)
            threading.Thread(
                target=run_quiz_test_loop, 
                args=(call.message.chat.id, questions, True), 
                daemon=True
            ).start()
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Xatolik yuz berdi: {e}")

    elif call.data == "user_quiz_group_info":
        bot.answer_callback_query(call.id)
        info_text = (
            "╭── 👥 **TESTNI GURUHINGIZDA O'TKAZISH TARTIBI** ──╮\n\n"
            "1. Botingizni o'zingizning guruhingizga qo'shing.\n"
            "2. Botga guruhda **Admin** huquqini bering (so'rovnoma yuborishi uchun).\n"
            "3. Guruh chatida `/quiz_start` buyrug'ini yuboring.\n"
            "4. Bot guruhga e'lon tashlaydi va kamida 3 kishi «Men tayyorman» tugmasini bosgach, har biri ⏳ 40 soniyalik 30 talik test boshlanadi!\n\n"
            f"Rasmiy kanalimiz: {CHANNEL_USERNAME}\n"
            "╰──────────────────────────────────────────╯"
        )
        bot.send_message(call.message.chat.id, info_text, parse_mode="Markdown")

print("AI Tilshunos v9.1 faol ishga tushdi...")
bot.infinity_polling()

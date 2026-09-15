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
    return "AI Tilshunos & Metodist v6.3 (Dynamic Quiz Edition) Faol!"

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

# --- ZAMONAVIY POST IMZOSI (CARD STYLE) ---
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

# --- FOYDALANUVCHILAR BAZASI ---
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_user(user):
    users = load_users()
    u_id = str(user.id)
    if u_id not in users:
        users[u_id] = {
            "first_name": user.first_name or "",
            "username": user.username or "",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

# --- KREATIV VA STRUKTURALI MENYULAR ---
def get_main_menu(user_id=None):
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    markup.row(
        tele_types.KeyboardButton("📑 Ilmiy maqola (OAK)"),
        tele_types.KeyboardButton("📄 Ilmiy tezis (Konferensiya)")
    )
    markup.row(
        tele_types.KeyboardButton("📋 Dars ishlanmasi"),
        tele_types.KeyboardButton("📝 Esse tekshiruvi (50 ball)")
    )
    markup.row(
        tele_types.KeyboardButton("📜 G'azal tahlili"),
        tele_types.KeyboardButton("📐 Aruz vazni hisoblagich")
    )
    markup.row(
        tele_types.KeyboardButton("🏛 Qadimgi turkiy til"),
        tele_types.KeyboardButton("📖 So'z izohi (O'TIL)")
    )
    markup.row(
        tele_types.KeyboardButton("🔍 So'z etimologiyasi"),
        tele_types.KeyboardButton("🔤 Imlo va orfoepiya")
    )
    markup.row(
        tele_types.KeyboardButton("🎯 Interfaol metodlar"),
        tele_types.KeyboardButton("🧠 BMB Quiz Test")
    )
    if user_id and int(user_id) == int(ADMIN_ID):
        markup.row(tele_types.KeyboardButton("📊 Boshqaruv & Statistika"))
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

def get_action_inline():
    markup = tele_types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        tele_types.InlineKeyboardButton(text="📢 Kanalimiz", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
        tele_types.InlineKeyboardButton(text="✨ Yangi so'rov", callback_data="refresh_menu")
    )
    return markup

# --- NATIJANI CHIQARISH ---
def deliver_response(user_id, text):
    if len(text) > 3900:
        text = text[:3900] + "\n\n*(Davomi hajm chegarasi tufayli qisqartirildi)*"

    is_admin = False
    try:
        if int(user_id) == int(ADMIN_ID):
            is_admin = True
    except Exception:
        pass

    if is_admin:
        try:
            bot.send_message(CHANNEL_USERNAME, text, parse_mode="Markdown")
            bot.send_message(
                user_id, 
                f"✅ **Admin:** Ushbu material **{CHANNEL_USERNAME}** kanaliga e'lon qilindi!", 
                parse_mode="Markdown", 
                reply_markup=get_action_inline()
            )
        except Exception:
            bot.send_message(user_id, text, reply_markup=get_action_inline())
    else:
        try:
            bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=get_action_inline())
        except Exception:
            bot.send_message(user_id, text, reply_markup=get_action_inline())

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
    "Siz O'zbekiston Respublikasi Oliy attestatsiya komissiyasi (OAK) talablari bo'yicha bosh ilmiy ekspert, "
    "filologiya fanlari doktori, professor hamda umumta'lim maktablari uchun oliy toifali bosh metodistsiz.\n\n"
    "QAT'IY TALAB (MAQOLA VA TEZIS BO'YICHA):\n"
    "Foydalanuvchiga TAYYOR ILMIY MAQOLA YOKI TEZIS MATNINI ASLO YOZMANG! "
    "Faqat tadqiqotchi o'zi mustaqil yoza olishi uchun: puxta ilmiy reja, ilmiy apparat (maqsad, vazifalar), "
    "har bir qismni yozish tartibi va adabiyotlar tanlash metodikasini bering.\n\n"
    "QAT'IY TAQIQLAR:\n"
    "1. Diniy mazmundagi da'vatlar, fatvolar yoki bahslar mutlaqo taqiqlanadi.\n"
    "2. Siyosat, davlat boshqaruvi, davlat rahbari va amaldorlar shaxsi haqida ma'lumot berish taqiqlanadi.\n"
    "3. Ekstremizm, kamsitish va haqoratli mazmunlar qat'iyan rad etiladi.\n\n"
    "MATN DIZAYNI:\n"
    "Javoblarni aniq sarlavhalar, bo'lim ajratuvchilari, emojilar va Telegram Markdown uslubida estetik tarzda yetkazib bering."
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
        "Talablar: Telegram Markdown formatida, ko'rkam ramkalar va ilmiy uslubda, 2800 belgidan oshmasin. "
        "Oxirida '📚 Manba:' keltirilsin."
    )
    last_error_msg = ""
    models = ["gemini-3.6-flash"]
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
                last_error_msg = str(e)
                if "429" in last_error_msg or "RESOURCE_EXHAUSTED" in last_error_msg:
                    time.sleep(3)
                    continue
                elif "503" in last_error_msg or "UNAVAILABLE" in last_error_msg:
                    time.sleep(2)
                    continue
                else:
                    break
    raise Exception(f"AI Xatolik tafsiloti: {last_error_msg[:300]}")

# --- QUIZ TEST UCHUN TASODIFIY DOLZARB MAVZULAR RO'YXATI ---
QUIZ_TOPICS = [
    "Fonetika: unli va undoshlar tasnifi, tovush o'zgarishlari (tovush tushishi, ortishi, almashishi)",
    "Leksikologiya: paronimlar lug'ati, omonimlar, ma'nodosh so'zlar uslubiyati",
    "Morfologiya: fe'l nisbatlari, vazifa shakllari (ravishdosh, sifatdosh, harakat nomi)",
    "Morfologiya: ot va sifat yasovchi qo'shimchalar, ularning imlosi va ma'nolari",
    "Morfologiya: yordamchi so'z turkumlari (ko'makchi, bog'lovchi, yuklama) va ularning vazifalari",
    "Sintaksis: ergashgan qo'shma gap turlari (ega, kesim, to'ldiruvchi, aniqlovchi, hol ergash gaplar)",
    "Sintaksis: uyushiq bo'laklar, ajratilgan bo'laklar, kiritma va kiritmalar punktuatsiyasi",
    "Mumtoz adabiyot: Alisher Navoiy dostonlari syujeti, obrazlar tizimi va g'azallari tahlili",
    "Mumtoz adabiyot: Zahiriddin Muhammad Bobur ruboiylari, g'azallari va 'Boburnoma' asari leksikasi",
    "Jadid adabiyoti: Cho'lpon she'riyati, Fitrat dramalari va Abdulla Qodiriy romanlari badiiyati",
    "XX asr o'zbek adabiyoti: Oybek, G'afur G'ulom, Said Ahmad, O'tkir Hoshimov asarlari",
    "She'r tuzilishi: aruz vazni bahrlaridagi ruknlar, hijolar va mumtoz she'riy san'atlar (tazod, tanosub, istiora, iyhom)",
    "Milliy sertifikat standarti: matnni tushunish, matndagi mantiqiy xatoni yoki asosiy g'oyani aniqlash"
]

# --- TAKRORLANMAYDIGAN QUIZ GENERATORI ---
def generate_ai_quiz():
    chosen_topic = random.choice(QUIZ_TOPICS)
    random_seed = random.randint(1000, 99999)

    prompt = (
        f"Siz BMB (DTM) va Ona tili hamda adabiyot Milliy sertifikati bo'yicha bosh tuzuvchisiz.\n"
        f"Aynan quyidagi mavzu bo'yicha 1 ta mutlaqo yangi, takrorlanmas, o'ta qiziqarli va darslik mezonidagi Quiz test tuzing:\n"
        f"👉 Mavzu: '{chosen_topic}'\n"
        f"Unikal kod: #{random_seed}\n\n"
        "Qat'iy talablar:\n"
        "1. Diniy, siyosiy yoki noo'rin mavzulardan mutlaqo chetlaning.\n"
        "2. Oldin tuzilgan odatiy testlarni takrorlamang, savol fikrlashga undaydigan chuqur darajada bo'lsin.\n"
        "3. Faqat quyidagi JSON formatida javob bering (boshqa hech qanday so'z qo'shmang):\n"
        "{\n"
        '  "question": "Savol matni (aniq, imloviy to\'g\'ri)",\n'
        '  "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob izohi va qaysi qoidaga asoslangani (180 belgidan oshmasin)"\n'
        "}\n"
        "Eslatma: correct_option_id faqat 0, 1, 2 yoki 3 bo'lsin."
    )
    models = ["gemini-3.6-flash"]
    last_error_msg = ""
    for model_name in models:
        for attempt in range(3):
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.85  # Savollar har safar xilma-xil va yangi chiqishi uchun
                    )
                )
                raw = response.text.strip()
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                return json.loads(raw)
            except Exception as e:
                last_error_msg = str(e)
                if "429" in last_error_msg or "RESOURCE_EXHAUSTED" in last_error_msg:
                    time.sleep(3)
                    continue
                elif "503" in last_error_msg or "UNAVAILABLE" in last_error_msg:
                    time.sleep(2)
                    continue
                else:
                    break
    raise Exception(f"Quiz tizimida xato: {last_error_msg[:300]}")

# --- KANAL JADVALI (AVTOPOSTING) ---
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
    users = load_users()
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

    users = load_users()
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

    user_name = message.from_user.first_name or "Hurmatli tadqiqotchi"
    text = (
        f"╭──── ✨ **Xush kelibsiz, {user_name}!** ────╮\n\n"
        "🏛 **AI TILSHUNOS & METODIST (v6.3)** — filologiya, adabiyot "
        "va pedagogika yo'nalishidagi eng ilg'or intellektual yordamchi.\n\n"
        "🔹 **Ilmiy tadqiqot:** OAK maqola va konferensiya tezislari rejasi\n"
        "🔹 **Metodik mahorat:** Dars ishlanmalari va 50 ballik esse tahlili\n"
        "🔹 **Mumtoz meros:** G'azal badiiyati, aruz vazni va bahrlar\n"
        "🔹 **Leksikologiya:** Eski turkiy til, O'TIL va etimologik sharhlar\n\n"
        "👇 *Quyidagi menyudan kerakli bo'limni tanlang:* \n"
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

    bot.reply_to(message, "⚡️ *Filologik tahlil jarayoni boshlandi, biroz kuting...*", parse_mode="Markdown")
    try:
        final_prompt = prompt_template.format(input=user_input)
        result = generate_ai_content(final_prompt, chat_id=message.chat.id)
        deliver_response(message.from_user.id, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")

# --- ASOSIY MENYU ISHLOVCHISI ---
@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    save_user(message.from_user)

    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = message.text

    if text == "🔙 Asosiy menyu":
        bot.send_message(message.chat.id, "📋 Asosiy boshqaruv menyusi:", reply_markup=get_main_menu(message.from_user.id))
        return

    elif text == "📊 Boshqaruv & Statistika" and int(message.from_user.id) == int(ADMIN_ID):
        show_admin_stats(message.chat.id)
        return

    # 1. ILMIY MAQOLA
    elif text == "📑 Ilmiy maqola (OAK)":
        bot.send_message(
            message.chat.id, 
            "📑 **OAK talabidagi Ilmiy maqola konstruktori:**\n\n"
            "> Ushbu bo'limda tadqiqot mavzusi bo'yicha IMRAD standarti asosidagi puxta reja va ilmiy yo'riqnoma beriladi.\n\n"
            "Kerakli usulni tanlang:", 
            parse_mode="Markdown",
            reply_markup=get_sub_menu("maqola")
        )

    elif text == "✍️ Mavzuni kiritish":
        msg = bot.reply_to(
            message,
            "✍️ **Ilmiy tadqiqot mavzusini kiriting:**\n\n"
            "Masalan: *«Boburnoma asarida fitonimlar lingvomadaniyati»*\n\n"
            "Mavzuni yozib yuboring:"
        )
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

    # 2. ILMIY TEZIS
    elif text == "📄 Ilmiy tezis (Konferensiya)":
        bot.send_message(
            message.chat.id, 
            "📄 **Konferensiya tezislari bo'limi:**\n\n"
            "> 1-2 sahifalik ixcham, teran va xalqaro talablarga mos tezis tuzilishi va yo'riqnomasi.\n\n"
            "Kerakli usulni tanlang:",
            parse_mode="Markdown",
            reply_markup=get_sub_menu("tezis")
        )

    elif text == "✍️ Tezis mavzusini kiritish":
        msg = bot.reply_to(
            message,
            "✍️ **Tezis mavzusi yoki asosiy ilmiy g'oyani kiriting:**"
        )
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

    # 3. DARS ISHLANMASI
    elif text == "📋 Dars ishlanmasi":
        bot.send_message(message.chat.id, "📋 **45 daqiqalik dars ishlanmasi (Konspekt):**", reply_markup=get_sub_menu("konspekt"))

    elif text == "✍️ Mavzuni kiritaman" and message.reply_to_message is None:
        msg = bot.reply_to(
            message, 
            "📋 Sinf va dars mavzusini yozing (Masalan: *«9-sinf. Ergashgan qo'shma gaplar tahlili»*):"
        )
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

    # 4. ESSE TEKSHIRUVI
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

    # 5. G'AZAL TAHLILI
    elif text == "📜 G'azal tahlili":
        bot.send_message(message.chat.id, "📜 **Mumtoz g'azal va baytlar sharhi:**", reply_markup=get_sub_menu("gazal"))

    elif text == "✍️ Baytni yuborish":
        msg = bot.reply_to(message, "✍️ Badiiy tahlil qilmoqchi bo'lgan baytingizni yuboring:")
        p = "Ushbu mumtoz baytni badiiy tahlil qiling: '{input}'. San'atlari, falsafiy ma'nosi va so'zlar sharhini bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy mumtoz bayt":
        bot.reply_to(message, "⏳ *Mumtoz adabiyotimizdan nodir bayt olinmoqda...*", parse_mode="Markdown")
        p = "Alisher Navoiy yoki Bobur ijodidan 1-2 bayt keltirib, uning badiiy san'atlari va falsafiy teranligini sharhlang."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    # 6. ARUZ VAZNI HISOBAGICH
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

    # 7. QADIMGI TURKIY TIL
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

    # 8. SO'Z IZOHI (O'TIL)
    elif text == "📖 So'z izohi (O'TIL)":
        bot.send_message(message.chat.id, "📖 **O'zbek tilining izohli lug'ati (O'TIL):**", reply_markup=get_sub_menu("izoh"))

    # 9. SO'Z ETIMOLOGIYASI
    elif text == "🔍 So'z etimologiyasi":
        bot.send_message(message.chat.id, "🔍 **Shavkat Rahmatullayev etimologik lug'ati:**", reply_markup=get_sub_menu("etimologiya"))

    elif text == "🎲 Tasodifiy etimologiya":
        bot.reply_to(message, "⏳ *Qiziqarli so'z etimologiyasi tadqiq qilinmoqda...*", parse_mode="Markdown")
        p = "O'zbek tilidagi qiziqarli bir so'zning tarixiy kelib chiqishi, o'zagi va ma'no taraqqiyotini etimologik jihatdan tushuntirib bering."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    # 10. IMLO VA ORFOEPIYA
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

    # 11. INTERFAOL METODLAR
    elif text == "🎯 Interfaol metodlar":
        bot.send_message(message.chat.id, "🎯 **Zamonaviy pedagogik texnologiyalar:**", reply_markup=get_sub_menu("metod"))

    elif text == "🎲 Tasodifiy metod":
        bot.reply_to(message, "⏳ *Interfaol metod shakllantirilmoqda...*", parse_mode="Markdown")
        p = "Ona tili yoki adabiyot darslari uchun zamonaviy interfaol metod ishlab chiqing: Metod nomi, Maqsadi, Bosqichlari va Topshiriq namunasi."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    # 12. BMB QUIZ TEST (DINAMIK VA TAKRORLANMAYDIGAN)
    elif text == "🧠 BMB Quiz Test":
        bot.reply_to(message, "⏳ *BMB standarti asosida yangi test tuzilmoqda...*", parse_mode="Markdown")
        try:
            quiz = generate_ai_quiz()
            is_admin = (int(message.from_user.id) == int(ADMIN_ID))
            target_chat = CHANNEL_USERNAME if is_admin else message.chat.id
            bot.send_poll(
                chat_id=target_chat,
                question=quiz["question"],
                options=quiz["options"],
                type="quiz",
                correct_option_id=quiz["correct_option_id"],
                explanation=quiz.get("explanation", ""),
                is_anonymous=True
            )
            if is_admin:
                bot.reply_to(message, f"✅ Test {CHANNEL_USERNAME} kanaliga e'lon qilindi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Test tuzishda xatolik: {e}")

    # UMUMIY SO'Z KIRITISH VARIANTLARI (IZOH VA ETIMOLOGIYA UCHUN)
    elif text == "✍️ So'zni kiritish":
        msg = bot.reply_to(message, "✍️ Qaysi so'z tahlili kerak? So'zni yozing:")
        p = "O'zbek tilining izohli lug'ati asosida '{input}' so'zining to'liq ma'nolari va namunaviy gaplarni keltiring."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy O'TIL so'zi":
        bot.reply_to(message, "⏳ *Izohli lug'atdan so'z tanlanmoqda...*", parse_mode="Markdown")
        p = "O'TIL lug'atidan boy ma'noli 1 ta so'zni tanlab, uning to'liq izohini berib o'ting."
        deliver_response(message.from_user.id, generate_ai_content(p, chat_id=message.chat.id))

    else:
        bot.send_message(message.chat.id, "Iltimos, menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu(message.from_user.id))

print("AI Tilshunos v6.3 (Dynamic Quiz Edition) faol ishga tushdi...")
bot.infinity_polling()

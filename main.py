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
    return "AI Tilshunos & Metodist v5.1 (Academic Guidance Edition) Faol!"

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
            print("Server uyg'oq holatda saqlanmoqda (Self-ping)...")
        except Exception as e:
            print(f"Ping xatosi: {e}")

threading.Thread(target=keep_alive, daemon=True).start()

# --- ASOSIY SOZLAMALAR ---
TELEGRAM_TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@onatilidanyordam"
ADMIN_ID = 5423849679

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

USERS_FILE = "users.json"

IMZO = (
    "\n\n━━━━━━━━━━━━━━━━━━━━\n"
    f"🏛 **Rasmiy kanal:** {CHANNEL_USERNAME}\n"
    "✨ **Pedagogik & Ilmiy bot:** @aitilshunosbot"
)

# --- TAQIQLANGAN MAVZULAR FILTRI (XAVFSIZLIK QALQONI) ---
FORBIDDEN_KEYWORDS = [
    # Siyosat va davlat boshqaruvi
    "prezident", "mirziyoyev", "hokim", "vazir", "hukumat", "davlat boshqaruvi", 
    "siyosat", "saylov", "muxolifat", "deputat", "amaldor", "partiya",
    # Din va e'tiqod
    "din", "islom", "namoz", "hadis", "oyat", "qur'on", "shariat", "masjid",
    "xristian", "cherkov", "yahudiy", "fatvo", "ro'za", "mulla", "imom",
    # Ekstremizm, terrorizm va noqonuniy faoliyat
    "ekstremizm", "terrorizm", "jihod", "vahobiy", "hizb", "inqilob", "qurol", "portlash",
    # Haqorat, kamsitish va etika buzilishi
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
    "⚠️ **XAVFSIZLIK VA ETIKA BILDIRISHNOMASI:**\n\n"
    "Ushbu bot faqat **tilshunoslik, adabiyotshunoslik va pedagogika** yo'nalishidagi "
    "ilmiy-metodik yordam uchun mo'ljallangan.\n\n"
    "❌ *Diniy, siyosiy, davlat boshqaruvi va amaldorlar faoliyati, shuningdek shaxs sha'nini "
    "kamsituvchi, haqoratli yoki ekstremistik mazmundagi so'rovlar qat'iyan taqiqlanadi!*"
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
        except Exception as e:
            print(f"Foydalanuvchini saqlashda xato: {e}")

# --- ZAMONAVIY MENYULAR TUZILISHI ---
def get_main_menu(user_id=None):
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        tele_types.KeyboardButton("📑 Ilmiy maqola (OAK)"),
        tele_types.KeyboardButton("📄 Ilmiy tezis (Konferensiya)")
    )
    markup.add(
        tele_types.KeyboardButton("📋 Dars ishlanmasi (Konspekt)"),
        tele_types.KeyboardButton("📝 Esse tekshiruvi (BMB)")
    )
    markup.add(
        tele_types.KeyboardButton("🎯 Interfaol metodlar"),
        tele_types.KeyboardButton("📜 G'azal va bayt tahlili")
    )
    markup.add(
        tele_types.KeyboardButton("📐 Aruz vazni tahlili"),
        tele_types.KeyboardButton("🏛 Qadimgi turkiy leksika")
    )
    markup.add(
        tele_types.KeyboardButton("📖 So'z izohi (O'TIL)"),
        tele_types.KeyboardButton("🔍 So'z etimologiyasi")
    )
    markup.add(
        tele_types.KeyboardButton("🔤 Imlo va orfoepiya"),
        tele_types.KeyboardButton("🧠 BMB Quiz Test")
    )
    if user_id and int(user_id) == int(ADMIN_ID):
        markup.add(tele_types.KeyboardButton("📊 Statistika (Admin)"))
    return markup

def get_sub_menu(category):
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    labels = {
        "maqola": ("✍️ Maqola mavzusini kiritish", "🎲 Tasodifiy maqola mavzusi"),
        "tezis": ("✍️ Tezis mavzusini kiritish", "🎲 Tasodifiy tezis mavzusi"),
        "konspekt": ("✍️ Mavzuni o'zim kiritaman", "🎲 Tasodifiy konspekt"),
        "esse": ("✍️ Esse matnini kiritish", "🎲 Tasodifiy esse tahlili"),
        "metod": ("✍️ Mavzuni o'zim kiritaman", "🎲 Tasodifiy metod"),
        "gazal": ("✍️ Baytni o'zim kiritaman", "🎲 Tasodifiy g'azal"),
        "aruz": ("✍️ Baytni kiritish", "🎲 Namunaviy aruz bayti"),
        "qadim": ("✍️ Tarixiy so'zni kiritish", "🎲 Tasodifiy qadimgi so'z"),
        "izoh": ("✍️ So'zni o'zim kiritaman", "🎲 Tasodifiy so'z izohi"),
        "etimologiya": ("✍️ So'zni o'zim kiritaman", "🎲 Tasodifiy etimologiya"),
        "imlo": ("✍️ So'z/gapni kiritish", "🎲 Tasodifiy qiyin so'z")
    }
    btn1, btn2 = labels.get(category, ("✍️ O'zim kiritaman", "🎲 Tasodifiy"))
    markup.add(tele_types.KeyboardButton(btn1), tele_types.KeyboardButton(btn2))
    markup.add(tele_types.KeyboardButton("🔙 Asosiy menyu"))
    return markup

# --- NATIJANI YO'NALTIRISH ---
def deliver_response(user_id, text):
    if len(text) > 3900:
        text = text[:3900] + "...\n*(Davomi qisqartirildi)*"

    is_admin = False
    try:
        if int(user_id) == int(ADMIN_ID):
            is_admin = True
    except Exception:
        pass

    if is_admin:
        try:
            bot.send_message(CHANNEL_USERNAME, text, parse_mode="Markdown")
            bot.send_message(user_id, f"✅ Admin ruxsati bilan ushbu post **{CHANNEL_USERNAME}** kanaliga ham e'lon qilindi!", parse_mode="Markdown")
        except Exception:
            bot.send_message(CHANNEL_USERNAME, text)
            bot.send_message(user_id, f"✅ Natija {CHANNEL_USERNAME} kanaliga chiqarildi.")
    else:
        try:
            bot.send_message(user_id, text, parse_mode="Markdown")
        except Exception:
            bot.send_message(user_id, text)

# --- MAJBURIY OBUNA TEKSHIRUVI ---
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
            text="✨ Kanalga obuna bo'lish", 
            url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        ),
        tele_types.InlineKeyboardButton(
            text="🔄 Obunani tasdiqlash", 
            callback_data="check_sub"
        )
    )
    matn = (
        "╔════════════════════════════╗\n"
        "   🏛 **AI TILSHUNOS ILMIY MARKAZI**\n"
        "╚════════════════════════════╝\n\n"
        "Bot xizmatlaridan to'liq foydalanish uchun rasmiy kanalimizga a'zo bo'ling.\n\n"
        f"Kanalimiz: {CHANNEL_USERNAME}"
    )
    bot.send_message(chat_id, matn, parse_mode="Markdown", reply_markup=markup)

# --- TIZIMNING XAVFSIZLIK VA AKADEMIK YO'RIQNOMASI ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi Oliy attestatsiya komissiyasi (OAK) talablari bo'yicha bosh ilmiy maslahatchi, "
    "filologiya fanlari doktori, professor hamda maktab va litseylar uchun oliy toifali bosh metodistsiz.\n\n"
    "QAT'IY ILMIY TALAB (MAQOLA VA TEZIS BO'YICHA):\n"
    "Ilmiy maqola va tezis so'ralganda FOYDALANUVCHIGA HECH QACHON TAYYOR MATN YOZIB BERMANG! "
    "Tadqiqotchi o'zi mustaqil yozishi uchun unga: puxta mantiqiy reja, har bir qismni (Kirish, Metodologiya, Tahlil, Xulosa) "
    "qanday yozish bo'yicha qadamma-qadam ilmiy ko'rsatma, ilmiy apparatni (obyekt, predmet, maqsad) to'g'ri shakllantirish tartibi "
    "va qaysi manbalarga tayanish kerakligi bo'yicha aniq metodik tavsiyalar bering.\n\n"
    "QAT'IY TAQIQLAR VA XAVFSIZLIK QOIDALARI:\n"
    "1. Diniy mazmundagi har qanday targ'ibot, aqidalar, fatvolar yoki diniy bahslar mutlaqo taqiqlanadi.\n"
    "2. Siyosat, O'zbekiston Respublikasining amaldagi davlat boshqaruvi, davlat rahbari va davlat amaldorlari shaxsi, "
    "har qanday siyosiy sharhlar qat'iyan man etiladi.\n"
    "3. Ekstremizm, terrorizm, milliy yoki etnik adovat g'oyalarini targ'ib qiluvchi har qanday matn taqiqlanadi.\n"
    "4. Inson sha'nini kamsituvchi, haqoratli iboralar mutlaqo rad etiladi.\n"
    "Agar foydalanuvchi taqiqlangan mavzularda so'rov yuborsa, odob bilan faqat tilshunoslik, adabiyotshunoslik yoki pedagogik "
    "yo'nalishlarda xizmat ko'rsata olishingizni bildiring.\n\n"
    "BOSHQA BO'LIMLAR:\n"
    "- Dars ishlanmasi: DTS talablari, 45 daqiqalik bosqichlar va ilg'or metodlar.\n"
    "- Esse tahlili: 50 ballik rasmiy mezon (Mavzu, Dalil, Mantiq, Savodxonlik) asosida.\n"
    "- Har bir javob oxirida '📚 Manba:' qismi keltirilsin."
)

# --- GEMINI AI GENERATSIYA FUNKSIYASI ---
def generate_ai_content(prompt_text):
    if check_security_violation(prompt_text):
        return SECURITY_WARNING

    full_prompt = (
        f"{prompt_text}\n\n"
        "Talablar: Telegram Markdown formatida, chiroyli sarlavhalar va ilmiy tilda, 2800 belgidan oshmasin. "
        "Oxirida '📚 Manba:' keltirilsin."
    )
    last_error_msg = ""
    models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    for model_name in models:
        for attempt in range(2):
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
                print(f"Xatolik ({model_name}): {e}")
                if "429" in last_error_msg or "RESOURCE_EXHAUSTED" in last_error_msg:
                    time.sleep(3)
                    continue
                elif "503" in last_error_msg or "UNAVAILABLE" in last_error_msg:
                    time.sleep(2)
                    continue
                else:
                    break
    raise Exception(f"AI Xatolik tafsiloti: {last_error_msg[:300]}")

def generate_ai_quiz():
    prompt = (
        "Ona tili yoki Adabiyot fanidan BMB (DTM) mezonida 4 variantli (A, B, C, D) 1 ta Quiz test tuzing. "
        "Diniy va siyosiy mavzulardan mutlaqo chetlaning. Faqat lingvistik yoki adabiy manbalardan foydalaning. "
        "Faqat quyidagi JSON formatida javob bering:\n"
        "{\n"
        '  "question": "Savol matni",\n'
        '  "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob izohi va manbasi (180 belgidan oshmasin)"\n'
        "}\n"
        "correct_option_id 0, 1, 2 yoki 3 bo'lsin."
    )
    models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    last_error_msg = ""
    for model_name in models:
        for attempt in range(2):
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.3
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
    raise Exception(f"Test tuzishda xatolik: {last_error_msg[:300]}")

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
                bot.send_message(CHANNEL_USERNAME, "🧠 **KECHKI INTELLEKT: BMB STANDARDIDAGI TESTLAR BOSHLANDI!**")
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
    for idx, (uid, data) in enumerate(list(users.items())[-10:], 1):
        uname = f"@{data['username']}" if data.get("username") else "usernamesiz"
        fname = data.get("first_name", "Noma'lum")
        date_str = data.get("date", "")
        last_users_text += f"{idx}. {fname} ({uname}) | ID: `{uid}` ({date_str})\n"

    if not last_users_text:
        last_users_text = "Hozircha foydalanuvchilar ro'yxati shakllanmagan."

    msg = (
        "╔════════════════════════════╗\n"
        "   📊 **ADMINISTRATOR STATISTIKASI**\n"
        "╚════════════════════════════╝\n\n"
        f"🤖 **Bot foydalanuvchilari:** `{total_users}` nafar\n"
        f"📢 **{CHANNEL_USERNAME} a'zolari:** `{channel_members}` nafar\n\n"
        "👥 **Oxirgi qo'shilgan 10 nafar a'zo:**\n"
        f"{last_users_text}\n"
        "────────────────────────\n"
        "📢 *Barcha a'zolarga xabar yo'llash:* `/send xabar matni`"
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
        bot.reply_to(message, "Xabar matnini kiriting. Masalan: `/send Assalomu alaykum!`", parse_mode="Markdown")
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

    text = (
        "╔════════════════════════════╗\n"
        "  ✨ **AI TILSHUNOS & METODIST v5.1**\n"
        "  🏛 *Oliy Ilmiy va Pedagogik Markaz*\n"
        "╚════════════════════════════╝\n\n"
        "Assalomu alaykum, hurmatli ustoz, tadqiqotchi va izlanuvchi!\n\n"
        "Botimiz sizga filologiya, metodika va tilshunoslik bo'yicha quyidagi xizmatlarni taqdim etadi:\n\n"
        "▫️ **Ilmiy maqola (OAK)** va **Tezis** bo'yicha reja va metodik yo'riqnomalar\n"
        "▫️ **Dars ishlanmasi** va **Esse tekshiruvi (50 ball)**\n"
        "▫️ **Aruz vazni** va **Mumtoz g'azal tahlili**\n"
        "▫️ **Qadimgi turkiy leksika** va **Etimologik tahlil**\n"
        "▫️ **O'TIL izohlari**, **Imlo me'yorlari** va **BMB Quizlar**\n\n"
        "⚠️ *Botda siyosiy, diniy, ekstremistik va haqoratli mavzular qat'iyan taqiqlangan.*\n\n"
        "👇 **Quyidagi bo'limlardan birini tanlang:**"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
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

# --- FOYDALANUVCHI MATN KIRITISH BOSQICHI ---
def process_custom_step(message, prompt_template):
    user_input = message.text.strip()
    if user_input == "🔙 Asosiy menyu":
        send_welcome(message)
        return

    if check_security_violation(user_input):
        bot.reply_to(message, SECURITY_WARNING, parse_mode="Markdown")
        return

    bot.reply_to(message, "⏳ Ilmiy-tahliliy jarayon davom etmoqda, iltimos kuting...")
    try:
        final_prompt = prompt_template.format(input=user_input)
        result = generate_ai_content(final_prompt)
        deliver_response(message.from_user.id, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")

# --- ASOSIY MENYU VA BUYRUQLAR ---
@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    save_user(message.from_user)

    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = message.text

    if text == "🔙 Asosiy menyu":
        bot.send_message(message.chat.id, "Asosiy menyuga qaytdingiz:", reply_markup=get_main_menu(message.from_user.id))
        return

    elif text == "📊 Statistika (Admin)" and int(message.from_user.id) == int(ADMIN_ID):
        show_admin_stats(message.chat.id)
        return

    # 1. ILMIY MAQOLA (REJA VA KO'RSATMA)
    elif text == "📑 Ilmiy maqola (OAK)":
        bot.send_message(message.chat.id, "📑 **OAK talabidagi Ilmiy maqola bo'limi:**\n*(Maqola uchun reja, ilmiy apparat va yozish yo'riqnomasi beriladi)*\nTanlang:", reply_markup=get_sub_menu("maqola"))

    elif text == "✍️ Maqola mavzusini kiritish":
        msg = bot.reply_to(
            message,
            "✍️ **Ilmiy maqola rejasi va ko'rsatmasi:**\n\n"
            "Tadqiqot mavzuingizni yozib yuboring (Masalan: *'O'zbek tilida fitonimlar semantikasi'*):"
        )
        p = (
            "O'zbekiston Respublikasi OAK talablari va xalqaro IMRAD standarti asosida '{input}' mavzusida ilmiy maqola yozish uchun METODIK KO'RSATMA VA ILMIY REJA loyihasini ishlab chiqing.\n\n"
            "QAT'IY TALAB: Tayyor maqola matnini aslo yozmang! Faqat muallif mustaqil yozishi uchun quyidagi tuzilishda yo'riqnoma bering:\n"
            "1. Tavsiya etiladigan ilmiy reja (IMRAD strukturasida: Kirish, Metodologiya, Tahlil va natijalar, Xulosa);\n"
            "2. Tadqiqotning ilmiy apparati (dolzarbligi, obyekti, predmeti, maqsadi va vazifalarini qanday shakllantirish bo'yicha ko'rsatma);\n"
            "3. Annotatsiya va kalit so'zlarni shakllantirish qoidalari;\n"
            "4. Tahlil qismida qaysi lingvistik/adabiy metodlardan va qanday empirik materiallardan foydalanish tavsiyalari;\n"
            "5. Xulosa qismida ilmiy yangilikni qay tarzda ifodalash ko'rsatmasi;\n"
            "6. OAK standarti bo'yicha foydalanilishi lozim bo'lgan asosiy ilmiy adabiyotlar va bibliografik manbalar yo'nalishi."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy maqola mavzusi":
        bot.reply_to(message, "⏳ Zamonaviy tilshunoslik yoki adabiyotshunoslik bo'yicha dolzarb mavzu va uning metodik rejasi shakllanmoqda...")
        p = (
            "O'zbek tilshunosligi yoki adabiyotshunosligi bo'yicha dolzarb bir mavzuni tanlang. "
            "Ushbu mavzuda OAK talablariga mos ilmiy maqola yozish uchun: puxta ilmiy reja, ilmiy apparat (maqsad, vazifa) va qadamma-qadam yozish yo'riqnomasini (metodik ko'rsatma) taqdim eting. "
            "Tayyor maqola matnini yozmang, faqat reja va yo'riqnoma bering."
        )
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 2. ILMIY TEZIS (REJA VA KO'RSATMA)
    elif text == "📄 Ilmiy tezis (Konferensiya)":
        bot.send_message(message.chat.id, "📄 **Konferensiyalar uchun Tezis bo'limi:**\n*(Tezis kompozitsiyasi, rejasi va yozish tartibi beriladi)*\nTanlang:", reply_markup=get_sub_menu("tezis"))

    elif text == "✍️ Tezis mavzusini kiritish":
        msg = bot.reply_to(
            message,
            "✍️ **Ilmiy tezis rejasi va yo'riqnomasi:**\n\n"
            "Konferensiya uchun tezis mavzusi yoki asosiy g'oyani yozing:"
        )
        p = (
            "Xalqaro va Respublika ilmiy-amaliy konferensiyalari talabi asosida '{input}' mavzusida tezis yozish bo'yicha METODIK KO'RSATMA VA REJA tayyorlang.\n\n"
            "QAT'IY TALAB: Tayyor tezis matnini yozmang! Faqat tadqiqotchi uchun yo'riqnoma bering:\n"
            "1. Tezisning ixcham va mantiqiy rejasi (1-2 sahifalik hajmga moslashtirilgan);\n"
            "2. Muammoning dolzarbligi va qo'yilishini 2-3 jumlada ifodalash qoidasi;\n"
            "3. Asosiy ilmiy dalil va yangi natijani tizimli bayon qilish ko'rsatmasi;\n"
            "4. Tezis yakunida ilmiy-amaliy taklif va xulosani shakllantirish tartibi."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy tezis mavzusi":
        bot.reply_to(message, "⏳ Konferensiya uchun dolzarb tezis mavzusi va rejasi tayyorlanmoqda...")
        p = (
            "Zamonaviy tilshunoslik yoki ona tili metodikasi bo'yicha bitta yangi ilmiy muammoni tanlang. "
            "Konferensiya talablariga mos tezis yozish uchun: reja, tezis kompozitsiyasi va qadamma-qadam yozish yo'riqnomasini taqdim eting. "
            "Tayyor tezis matnini yozmang, faqat reja va yo'riqnoma bering."
        )
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 3. DARS ISHLANMASI (KONSPEKT)
    elif text == "📋 Dars ishlanmasi (Konspekt)":
        bot.send_message(message.chat.id, "📋 **Dars ishlanmasi konstruktori:**\nTanlang:", reply_markup=get_sub_menu("konspekt"))

    elif text == "✍️ Mavzuni o'zim kiritaman" and message.reply_to_message is None:
        msg = bot.reply_to(
            message, 
            "📋 Sinf va dars mavzusini yozib yuboring (Masalan: *«8-sinf. Ergashgan qo'shma gaplar»*):"
        )
        p = (
            "Umumta'lim maktabi uchun '{input}' mavzusida to'liq 45 daqiqalik dars ishlanmasi (konspekt) tuzing:\n"
            "1. Dars maqsadi va DTS talablari;\n"
            "2. Dars jihozi va metodlari;\n"
            "3. Dars bosqichlari (vaqt taqsimoti, yangi mavzu, mustahkamlash, baholash va uyga vazifa)."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy konspekt":
        bot.reply_to(message, "⏳ Umumta'lim darsliklaridan namunaviy dars konspekti tayyorlanmoqda...")
        p = "Ona tili yoki adabiyot fanidan tasodifiy bir murakkab mavzuga 45 daqiqalik mukammal namunaviy dars konspektini tuzing."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 4. ESSE TEKSHIRUVI
    elif text == "📝 Esse tekshiruvi (BMB)":
        bot.send_message(message.chat.id, "📝 **Esse tekshiruvi (50 ballik mezon):**\nTanlang:", reply_markup=get_sub_menu("esse"))

    elif text == "✍️ Esse matnini kiritish":
        msg = bot.reply_to(
            message,
            "📝 Esse mavzusi va matnini to'liq yuboring:\n"
            "Bot uni 50 ballik rasmiy mezon bo'yicha tahlil qilib beradi."
        )
        p = (
            "Ushbu esse matnini BMB (DTM) ning 50 ballik mezonlari bo'yicha tekshiring:\n'{input}'\n\n"
            "Baholash: Mavzuni ochish (15 ball), Dalillar (10 ball), Mantiq (10 ball), Savodxonlik (15 ball), Jami ball va metodik xatolar sharhi."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy esse tahlili":
        bot.reply_to(message, "⏳ Namunaviy esse mavzusi va uning mukammal tahlili tuzilmoqda...")
        p = "Milliy sertifikat darajasidagi tasodifiy bir esse mavzusini tanlang, namunaviy esse matnini keltiring va uni 50 ballik mezon asosida tahlil qilib bering."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 5. INTERFAOL METODLAR
    elif text == "🎯 Interfaol metodlar":
        bot.send_message(message.chat.id, "🎯 **Interfaol metodlar bo'limi:**\nTanlang:", reply_markup=get_sub_menu("metod"))

    elif text == "🎲 Tasodifiy metod":
        bot.reply_to(message, "⏳ Qiziqarli va zamonaviy interfaol metod shakllantirilmoqda...")
        p = "Ona tili yoki adabiyot darsi uchun eng samarali va zamonaviy interfaol metod ishlab chiqing: Metod nomi, Maqsadi, Qo'llanish bosqichlari va Topshiriq namunasi."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 6. G'AZAL VA BAYT TAHLILI
    elif text == "📜 G'azal va bayt tahlili":
        bot.send_message(message.chat.id, "📜 **G'azal va mumtoz baytlar tahlili:**\nTanlang:", reply_markup=get_sub_menu("gazal"))

    elif text == "✍️ Baytni o'zim kiritaman":
        msg = bot.reply_to(message, "✍️ Tahlil qilmoqchi bo'lgan baytingizni yuboring:")
        p = "Ushbu baytni badiiy tahlil qiling: '{input}'. San'atlari, falsafiy ma'nosi va so'zlar izohini bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy g'azal":
        bot.reply_to(message, "⏳ Mumtoz adabiyotimizdan nodir bayt tanlanmoqda...")
        p = "Navoiy, Bobur yoki Ogahiy ijodidan 1-2 bayt keltirib, uning badiiy san'atlari va so'zlar sharhini bering."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 7. ARUZ VAZNI TAHLILI
    elif text == "📐 Aruz vazni tahlili":
        bot.send_message(message.chat.id, "📐 **Aruz vazni hisoblagich:**\nTanlang:", reply_markup=get_sub_menu("aruz"))

    elif text == "✍️ Baytni kiritish":
        msg = bot.reply_to(message, "✍️ Aruzini aniqlamoqchi bo'lgan baytni yuboring:")
        p = (
            "Ushbu baytni aruz tizimi bo'yicha tahlil qiling:\n'{input}'\n"
            "1. Bo'g'inlar turi (ochiq, yopiq, cho'ziq);\n2. Ruknlar va taf'ilalar;\n3. Vazn va bahr nomi."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Namunaviy aruz bayti":
        bot.reply_to(message, "⏳ Aruz bahrlariga oid mukammal tahlil tayyorlanmoqda...")
        p = "Aruz vaznidagi (masalan, Hazaj yoki Ramal bahrida) mashhur bir baytni olib, uning ruknlari, hijolari va vaznini tahlil qilib bering."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 8. QADIMGI TURKIY LEKSIKA
    elif text == "🏛 Qadimgi turkiy leksika":
        bot.send_message(message.chat.id, "🏛 **Qadimgi va eski turkiy tili leksikasi:**\nTanlang:", reply_markup=get_sub_menu("qadim"))

    elif text == "✍️ Tarixiy so'zni kiritish":
        msg = bot.reply_to(message, "✍️ Qaysi tarixiy yoki arxaik so'z ma'nosi kerak? So'zni yozing:")
        p = "'{input}' so'zini qadimgi turkiy yozma yodgorliklar va mumtoz asarlar asosida filologik tahlil qiling."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy qadimgi so'z":
        bot.reply_to(message, "⏳ 'Devonu lug'atit turk' yoki 'Boburnoma'dan nodir so'z olinmoqda...")
        p = "Qadimgi turkiy tilga oid 1 ta nodir arxaik so'zni tanlab, uning etimologiyasi, tarixiy ma'nosi va qo'llanishini yozing."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 9. SO'Z IZOHI (O'TIL)
    elif text == "📖 So'z izohi (O'TIL)":
        bot.send_message(message.chat.id, "📖 **O'zbek tilining izohli lug'ati (O'TIL):**\nTanlang:", reply_markup=get_sub_menu("izoh"))

    elif text == "✍️ So'zni o'zim kiritaman":
        msg = bot.reply_to(message, "✍️ Izohini bilmoqchi bo'lgan so'zingizni yozing:")
        p = "O'zbek tilining izohli lug'ati asosida '{input}' so'zining to'liq ma'nolari, shakllari va namunaviy gaplarni keltiring."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy so'z izohi":
        bot.reply_to(message, "⏳ Izohli lug'atdan qiziqarli so'z tanlanmoqda...")
        p = "O'TIL lug'atidan serqirra va boy ma'noli 1 ta so'zni tanlab, uning to'liq izohini berib o'ting."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 10. SO'Z ETIMOLOGIYASI
    elif text == "🔍 So'z etimologiyasi":
        bot.send_message(message.chat.id, "🔍 **Etimologik lug'at bo'limi:**\nTanlang:", reply_markup=get_sub_menu("etimologiya"))

    elif text == "🎲 Tasodifiy etimologiya":
        bot.reply_to(message, "⏳ Qiziqarli so'z etimologiyasi o'rganilmoqda...")
        p = "O'zbek tilidagi biror qiziqarli so'zning tarixiy kelib chiqishi, o'zagi va ma'no taraqqiyotini etimologik jihatdan tushuntirib bering."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 11. IMLO VA ORFOEPIYA
    elif text == "🔤 Imlo va orfoepiya":
        bot.send_message(message.chat.id, "🔤 **Imlo va orfoepiya qoidalari:**\nTanlang:", reply_markup=get_sub_menu("imlo"))

    elif text == "✍️ So'z/gapni kiritish":
        msg = bot.reply_to(message, "✍️ Tekshirmoqchi bo'lgan so'zingiz yoki jumlani yozing:")
        p = "'{input}' bo'yicha rasmiy imlo qoidasi, bo'g'in va urg'u ko'rsatkichlarini tushuntirib bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy qiyin so'z":
        bot.reply_to(message, "⏳ Imlo jihatdan ko'p adashiladigan so'z tahlili tayyorlanmoqda...")
        p = "Ko'pchilik yozishda xato qiladigan 1 ta qiyin so'z yoki birikmani olib, uning to'g'ri imlo va talaffuz qoidasini yozing."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 12. BMB QUIZ TEST
    elif text == "🧠 BMB Quiz Test":
        bot.reply_to(message, "⏳ BMB mezonidagi test shakllantirilmoqda...")
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

    else:
        bot.send_message(message.chat.id, "Iltimos, pastdagi menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu(message.from_user.id))

print("AI Tilshunos v5.1 (Academic Guidance Edition) faol ishga tushdi...")
bot.infinity_polling()

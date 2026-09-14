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

# --- RENDER WEB SERVICE PORTI UCHUN SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "AI Tilshunos & Metodist v4.4 (Admin, Stats & Error Diagnosis) Faol!"

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
    "\n\n────────────────\n"
    f"🌟 **Rasmiy kanal:** {CHANNEL_USERNAME}\n"
    "✨ **Pedagogik & Ilmiy bot:** @aitilshunosbot"
)

# --- FOYDALANUVCHILAR BAZASINI BOSHQARISH ---
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

# --- MENYULAR TUZILISHI ---
def get_main_menu(user_id=None):
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        tele_types.KeyboardButton("📋 Dars ishlanmasi (Konspekt)"),
        tele_types.KeyboardButton("📝 Esse tekshiruvi (BMB/Sertifikat)")
    )
    markup.add(
        tele_types.KeyboardButton("🎯 Interfaol metodlar"),
        tele_types.KeyboardButton("📜 G'azal va bayt tahlili")
    )
    markup.add(
        tele_types.KeyboardButton("📐 Aruz vazni tahlili"),
        tele_types.KeyboardButton("🏛 Eski turkiy leksikasi")
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
        "metod": ("✍️ Mavzuni o'zim kiritaman", "🎲 Tasodifiy metod"),
        "gazal": ("✍️ Baytni o'zim kiritaman", "🎲 Tasodifiy g'azal"),
        "izoh": ("✍️ So'zni o'zim kiritaman", "🎲 Tasodifiy so'z izohi"),
        "etimologiya": ("✍️ So'zni o'zim kiritaman", "🎲 Tasodifiy etimologiya"),
        "aruz": ("✍️ Baytni kiritish", "🔙 Asosiy menyu"),
        "qadim": ("✍️ Tarixiy so'zni kiritish", "🎲 Tasodifiy qadimgi so'z"),
        "imlo": ("✍️ So'z/gap imlosini tekshirish", "🔙 Asosiy menyu")
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
            bot.send_message(user_id, f"✅ Siz admin bo'lganingiz uchun ushbu post **{CHANNEL_USERNAME}** kanaliga e'lon qilindi!", parse_mode="Markdown")
        except Exception:
            bot.send_message(CHANNEL_USERNAME, text)
            bot.send_message(user_id, f"✅ Natija {CHANNEL_USERNAME} kanaliga chiqarildi.")
    else:
        try:
            bot.send_message(user_id, text, parse_mode="Markdown")
        except Exception:
            bot.send_message(user_id, text)

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
            text="✨ Kanalga obuna bo'lish", 
            url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        ),
        tele_types.InlineKeyboardButton(
            text="🔄 Obunani tasdiqlash", 
            callback_data="check_sub"
        )
    )
    matn = (
        "╔════════════════════════╗\n"
        "   🏛 **AI TILSHUNOS METODIK MARKAZI**\n"
        "╚════════════════════════╝\n\n"
        "Bot xizmatlaridan foydalanish uchun rasmiy kanalimizga a'zo bo'lishingiz lozim.\n\n"
        f"Kanal: {CHANNEL_USERNAME}"
    )
    bot.send_message(chat_id, matn, parse_mode="Markdown", reply_markup=markup)

# --- GEMINI SISTEMA KO'RSATMASI ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi maktab va litseylari Ona tili va adabiyoti fani bo'yicha "
    "bosh metodist, filolog-matnshunos olim va BMB/Milliy sertifikat bo'yicha oliy toifali ekspertisiz.\n"
    "ASOSIY TALABLAR:\n"
    "1. Dars ishlanmasi: DTS talablari, dars maqsadi, jihozlar va 45 daqiqalik dars bosqichlari aniq tuzilsin.\n"
    "2. Esse tekshiruvi: 50 ballik mezon (Mavzu: 15, Dalillar: 10, Mantiq: 10, Imlo/grammatika: 15) asosida baholansin.\n"
    "3. Aruz vazni: Hijolarni (ochiq, yopiq, cho'ziq), ruknlarini va bahr nomini aniq ko'rsating.\n"
    "4. Eski turkiy: 'Devonu lug'atit turk', Boburnoma va Navoiy leksikasi bo'yicha ma'no va etimologiya bering.\n"
    "5. Har bir javob oxirida '📚 Manba:' keltirilsin. Siyosiy va diniy mavzular qat'iyan taqiqlanadi."
)

# --- ANIQ XATOLIKNI KO'RSATUVCHI AI FUNKSIYASI ---
def generate_ai_content(prompt_text):
    full_prompt = (
        f"{prompt_text}\n\n"
        "Talablar: Telegram Markdown formatida, emojilar bilan, 2500 belgidan oshmasin. "
        "Oxirida '📚 Manba:' keltirilsin."
    )
    last_error_msg = ""
    models = ["gemini-2.5-flash", "gemini-2.0-flash"]
    for model_name in models:
        for attempt in range(2):
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
                last_error_msg = str(e)
                print(f"Xatolik qayd etildi ({model_name}): {e}")
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
        "Faqat quyidagi JSON formatida javob bering:\n"
        "{\n"
        '  "question": "Savol matni",\n'
        '  "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob izohi va darslik manbasi (180 belgidan oshmasin)"\n'
        "}\n"
        "correct_option_id 0, 1, 2 yoki 3 bo'lsin."
    )
    models = ["gemini-2.5-flash", "gemini-2.0-flash"]
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
    raise Exception(f"Test tizimida xato: {last_error_msg[:300]}")

# --- AVTOMATLASHGAN KANAL JADVALI (AUTO-POSTING) ---
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
                p = "Alisher Navoiy, Bobur yoki mumtoz allomalarimiz o'gitlaridan ilm, vaqt qadri va ustozlik haqida ibratli tonggi post yozing."
                matn = generate_ai_content(p)
                bot.send_message(CHANNEL_USERNAME, f"☀️ **KUN HIKMATI & TONGGI ILHOM**\n\n{matn}", parse_mode="Markdown")
                sent_flags["08:30"] = True

            elif current_time == "13:00" and not sent_flags["13:00"]:
                p = "O'zbek tilining izohli lug'ati yoki etimologik lug'at asosida bitta qiziqarli so'zning chuqur tahlilini (kun so'zi sifatida) taqdim eting."
                matn = generate_ai_content(p)
                bot.send_message(CHANNEL_USERNAME, f"📖 **KUN SO'ZI TAHLILI**\n\n{matn}", parse_mode="Markdown")
                sent_flags["13:00"] = True

            elif current_time == "17:00" and not sent_flags["17:00"]:
                p = "Ona tili yoki adabiyot fanidan tasodifiy mavzuga zamonaviy interfaol metod ishlab chiqing. Mavzu, Metod nomi, Darsdagi o'rni, Qo'llash tartibi va Topsiriqni bering."
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

# --- ADMIN STATISTIKA FUNKSIYASI ---
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
        last_users_text = "Hozircha foydalanuvchilar yo'q."

    msg = (
        "📊 **BOT VA KANAL STATISTIKASI (ADMIN)**\n"
        "────────────────────────\n"
        f"🤖 **Botdagi jami a'zolar soni:** `{total_users}` nafar\n"
        f"📢 **{CHANNEL_USERNAME} kanal a'zolari:** `{channel_members}` nafar\n\n"
        "👥 **Oxirgi qo'shilgan a'zolar:**\n"
        f"{last_users_text}\n"
        "────────────────────────\n"
        "📢 *Barcha a'zolarga xabar yuborish uchun:* `/send xabar matni`"
    )
    bot.send_message(chat_id, msg, parse_mode="Markdown")

# --- ADMIN BUYRUQLARI ---
@bot.message_handler(commands=['stat'])
def cmd_stat(message):
    if int(message.from_user.id) == int(ADMIN_ID):
        show_admin_stats(message.chat.id)
    else:
        bot.reply_to(message, "Bu buyruq faqat bot administratori uchun.")

@bot.message_handler(commands=['send'])
def broadcast_message(message):
    if int(message.from_user.id) != int(ADMIN_ID):
        return
    text_to_send = message.text.replace("/send", "").strip()
    if not text_to_send:
        bot.reply_to(message, "Xabar matnini kiriting. Masalan: `/send Assalomu alaykum, yangilik!`", parse_mode="Markdown")
        return

    users = load_users()
    success = 0
    bot.reply_to(message, f"📢 {len(users)} ta a'zoga xabar yuborilmoqda...")
    for uid in users.keys():
        try:
            bot.send_message(uid, text_to_send)
            success += 1
            time.sleep(0.05)
        except Exception:
            pass
    bot.send_message(message.chat.id, f"✅ Xabar muvaffaqiyatli tarqatildi!\nQabul qildi: {success} ta foydalanuvchi.")

@bot.message_handler(commands=['myid'])
def get_user_id(message):
    bot.reply_to(message, f"🆔 Sizning Telegram ID raqamingiz: `{message.from_user.id}`", parse_mode="Markdown")

# --- START VA OBUNA ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_user(message.from_user)

    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = (
        "╔════════════════════════╗\n"
        "  ✨ **AI TILSHUNOS & METODIST v4.4**\n"
        "╚════════════════════════╝\n\n"
        "Assalomu alaykum, aziz ustoz, tadqiqotchi va talaba!\n\n"
        "Botingiz quyidagi ilmiy va metodik xizmatlarni taqdim etadi:\n\n"
        "▫️ Dars ishlanmasi (Konspekt) konstruktori\n"
        "▫️ Esse tekshiruvi va 50 ballik tahlil (BMB)\n"
        "▫️ Aruz vazni va bahrlar tahlili\n"
        "▫️ Qadimgi va eski turkiy leksikasi\n"
        "▫️ Rasmiy imlo va orfoepiya qoidalari\n"
        "▫️ O'TIL, Etimologiya, G'azal tahlili va Quizlar\n\n"
        "👇 **Quyidagi tugmalardan kerakli bo'limni tanlang:**"
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

# --- FOYDALANUVCHI KIRITISH BOSQICHLARI ---
def process_custom_step(message, prompt_template):
    user_input = message.text.strip()
    if user_input == "🔙 Asosiy menyu":
        send_welcome(message)
        return
    bot.reply_to(message, "⏳ Tahlil tayyorlanmoqda, iltimos kuting...")
    try:
        final_prompt = prompt_template.format(input=user_input)
        result = generate_ai_content(final_prompt)
        deliver_response(message.from_user.id, result)
    except Exception as e:
        bot.reply_to(message, f"❌ {e}")

# --- ASOSIY MENYU VA BUYRUQLAR ---
@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    save_user(message.from_user)

    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = message.text

    if text == "🔙 Asosiy menyu":
        bot.send_message(message.chat.id, "Asosiy menyudasiz:", reply_markup=get_main_menu(message.from_user.id))
        return

    elif text == "📊 Statistika (Admin)" and int(message.from_user.id) == int(ADMIN_ID):
        show_admin_stats(message.chat.id)
        return

    elif text == "📋 Dars ishlanmasi (Konspekt)":
        msg = bot.reply_to(
            message, 
            "📋 **Dars konspekti konstruktori:**\n\n"
            "Qaysi sinf va mavzu bo'yicha konspekt kerak? Masalan:\n"
            "👉 *«8-sinf. Ergashgan qo'shma gaplar»* yoki *«10-sinf. Cho'lponning 'Kecha va kunduz' romani»*\n\n"
            "Sinf va mavzuni yozib yuboring:"
        )
        p = (
            "Umumta'lim maktabi uchun aynan '{input}' mavzusi bo'yicha to'liq va mukammal 45 daqiqalik DARS ISHLANMASI (konspekt) tuzing.\n"
            "Tuzilishi:\n"
            "1. Darsning maqsadlari (ta'limiy, tarbiyaviy, rivojlantiruvchi);\n"
            "2. DTS talabi va tayanch kompetensiyalar;\n"
            "3. Dars jihozi va usullari;\n"
            "4. Dars bosqichlari (Vaqt taqsimoti bilan: Tashkiliy qism, O'tilgan mavzuni so'rash, Yangi mavzu bayoni, Mustahkamlash mashqlari, Baholash, Uyga vazifa)."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "📝 Esse tekshiruvi (BMB/Sertifikat)":
        msg = bot.reply_to(
            message,
            "📝 **Esse tekshiruvi (BMB / Milliy sertifikat mezonida):**\n\n"
            "Yozgan esse matningizni (mavzusi bilan birga) to'liq yuboring.\n"
            "Bot uni 50 ballik mezon asosida tahlil qilib, xatolaringiz va ballingizni chiqarib beradi."
        )
        p = (
            "Quyida taqdim etilgan esseni BMB (DTM) va Milliy sertifikatning 50 ballik mezonlari asosida professional darajada tekshirib bering:\n\n"
            "Matn:\n'{input}'\n\n"
            "BAHOLASH TARTIBI:\n"
            "1. Mavzuning ochilishi va g'oyaviy teranlik (Maks: 15 ball);\n"
            "2. Adabiy asarlar va dalillardan foydalanish (Maks: 10 ball);\n"
            "3. Mantiqiy izchillik va kompozitsiya (Maks: 10 ball);\n"
            "4. Grammatik, uslubiy, orfografik va punktuatsion savodxonlik (Maks: 15 ball);\n"
            "JAMI BALL (0 dan 50 gacha);\n"
            "Aniqlangan kamchiliklar va muallifga metodik tavsiyalar."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "📐 Aruz vazni tahlili":
        msg = bot.reply_to(
            message,
            "📐 **Aruz vazni va bahr hisoblagich:**\n\n"
            "Tahlil qilmoqchi bo'lgan g'azal baytini yozib yuboring:"
        )
        p = (
            "Ushbu mumtoz baytni aruz vazni qoidalari bo'yicha to'liq ilmiy tahlil qiling:\n'{input}'\n\n"
            "Tahlil bosqichlari:\n"
            "1. Hijolarga ajratilishi (ochiq (V), yopiq (-) va cho'ziq (~));\n"
            "2. Ruknlarga bo'linishi (taf'ilalar: fa'uvlun, mafoyilun, foylun va h.k.);\n"
            "3. Vazn va bahr nomi (Masalan: Hazaji musammani solim);\n"
            "4. Baytning umumiy badiiy ma'nosi va so'zlar sharhi."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🏛 Eski turkiy leksikasi":
        bot.send_message(message.chat.id, "🏛 **Eski turkiy va Chig'atoy tili leksikasi:**\nTanlang:", reply_markup=get_sub_menu("qadim"))

    elif text == "✍️ Tarixiy so'zni kiritish":
        msg = bot.reply_to(message, "✍️ Qaysi tarixiy yoki arxaik so'z ma'nosi kerak? So'zni yozing:")
        p = (
            "'{input}' so'zini qadimgi turkiy va mumtoz adabiyot (Navoiy, Bobur, Devonu lug'atit turk) "
            "manbalari asosida tahlil qiling. Tarixiy ma'nosi, asarlardagi qo'llanish o'rni va hozirgi tildagi ekvivalentini tushuntiring."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy qadimgi so'z":
        bot.reply_to(message, "⏳ Qadimgi turkiy manbalardan nodir so'z tanlanmoqda...")
        p = "Mumtoz asarlarda (Boburnoma, Xamsa yoki Devonu lug'atit turk) uchraydigan tasodifiy 1 ta qiziqarli arxaik so'zni tanlab, uning to'liq filologik sharhini bering."
        deliver_response(message.from_user.id, generate_ai_content(p))

    elif text == "🔤 Imlo va orfoepiya":
        msg = bot.reply_to(
            message,
            "🔤 **Imlo va orfoepik maslahatchi:**\n\n"
            "Imlosiga yoki urg'usiga shubha qilayotgan so'zingiz yoki jumlani yozib yuboring (Masalan: *x/h*, tutuq belgisi, ajratib yoki qo'shib yozilishi):"
        )
        p = (
            "'{input}' bo'yicha rasmiy o'zbek tili imlo va orfoepiya mezonlari asosida tushuntirish bering:\n"
            "1. To'g'ri yozilishi va amaldagi imlo qoidasi;\n"
            "2. Urg'usi qaysi bo'g'inga tushishi (orfoepik me'yor);\n"
            "3. Ko'p yo'l qo'yiladigan xatolar va namunali gaplar."
        )
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎯 Interfaol metodlar":
        bot.send_message(message.chat.id, "🎯 **Interfaol metodlar bo'limi:**", reply_markup=get_sub_menu("metod"))

    elif text == "✍️ Mavzuni o'zim kiritaman":
        msg = bot.reply_to(message, "✍️ Qaysi mavzu bo'yicha metod kerak? Mavzu nomini yozing:")
        p = "Ona tili yoki adabiyot fanidan '{input}' mavzusi uchun zamonaviy interfaol metod ishlab chiqing: Mavzu, Metod nomi, Darsdagi o'rni, Qo'llash tartibi, Darslikdan topshiriq, Natija."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy metod":
        bot.reply_to(message, "⏳ Tasodifiy interfaol metod ishlab chiqilmoqda...")
        p = "Ona tili yoki adabiyot fanidan tasodifiy bir mavzuga qiziqarli interfaol metod ishlab chiqing. Mavzu, Metod nomi, Darsdagi o'rni, Bosqichlari va Topshiriqni bering."
        deliver_response(message.from_user.id, generate_ai_content(p))

    elif text == "📜 G'azal va bayt tahlili":
        bot.send_message(message.chat.id, "📜 **G'azal tahlili bo'limi:**", reply_markup=get_sub_menu("gazal"))

    elif text == "✍️ Baytni o'zim kiritaman":
        msg = bot.reply_to(message, "✍️ Tahlil qilmoqchi bo'lgan baytingizni yuboring:")
        p = "Ushbu baytni badiiy tahlil qiling: '{input}'. San'atlari (tazod, tanosub, istiora va b.), ma'nosi va so'zlar sharhini bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy g'azal":
        bot.reply_to(message, "⏳ Mumtoz g'azal tahlili tayyorlanmoqda...")
        p = "Mumtoz adabiyotimizdan (Navoiy, Bobur, Lutfiy yoki Ogahiy) 1-2 bayt keltirib, badiiy san'atlari, falsafiy ma'nosi va so'zlar sharhini yozing."
        deliver_response(message.from_user.id, generate_ai_content(p))

    elif text == "📖 So'z izohi (O'TIL)":
        msg = bot.reply_to(message, "📖 Izohli lug'at (O'TIL) bo'yicha tahlil qilish uchun so'zni yuboring:")
        p = "O'zbek tilining izohli lug'ati (O'TIL) asosida '{input}' so'zining to'liq leksik ma'nolari, uslubiy xoslanishi va matndan namunali gaplarni bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🔍 So'z etimologiyasi":
        msg = bot.reply_to(message, "🔍 Etimologiyasini bilmoqchi bo'lgan so'zingizni yuboring:")
        p = "Shavkat Rahmatullayevning 'O'zbek tilining etimologik lug'ati' asosida '{input}' so'zining tarixiy ildizi, o'zagi va ma'no taraqqiyotini tahlil qiling."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🧠 BMB Quiz Test":
        bot.reply_to(message, "⏳ BMB mezonidagi Quiz testi tuzilmoqda...")
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
            bot.reply_to(message, f"❌ {e}")

    else:
        bot.send_message(message.chat.id, "Iltimos, menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu(message.from_user.id))

print("AI Tilshunos v4.4 (Admin, Stats & Error Diagnosis) faol ishga tushdi...")
bot.infinity_polling()

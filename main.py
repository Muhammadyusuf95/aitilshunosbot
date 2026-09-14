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
    return "AI Tilshunos & Metodist v4.1 (gemini-3.6-flash) Faol!"

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
ADMIN_ID = 5423849679  # Sizning Telegram ID raqamingiz

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Rasmiy va amaldagi model
CURRENT_AI_MODEL = "gemini-3.6-flash"

IMZO = (
    "\n\n────────────────\n"
    f"🌟 **Rasmiy kanal:** {CHANNEL_USERNAME}\n"
    "✨ **Pedagogik & Ilmiy bot:** @aitilshunosbot"
)

# --- MENYULAR TUZILISHI ---
def get_main_menu():
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
    "1. Dars ishlanmasi: DTS talablari, dars maqsadi (ta'limiy, tarbiyaviy, rivojlantiruvchi), "
    "jihozlar va 45 daqiqalik dars bosqichlari (kirish, yangi mavzu, mustahkamlash, baholash, uyga vazifa) aniq tuzilsin.\n"
    "2. Esse tekshiruvi: 50 ballik mezon asosida (Mavzu ochilishi: 15 ball, Dalillar: 10 ball, "
    "Mantiq/kompozitsiya: 10 ball, Imlo/grammatika: 15 ball) qat'iy va asosli baholansin, aniq xatolar ko'rsatilsin.\n"
    "3. Aruz vazni: Hijolarni (ochiq (V), yopiq (-), cho'ziq (~)) qat'iy belgilab, ruknlarini va aruz bahrini (hazaj, ramal va h.k.) tushuntiring.\n"
    "4. Eski turkiy: 'Devonu lug'atit turk', Boburnoma va Navoiy asarlari leksikasi bo'yicha tarixiy o'zak va ma'no bering.\n"
    "5. Har bir javob oxirida '📚 Manba:' keltirilsin. Siyosiy, diniy, davlatga zid mavzular qat'iyan taqiqlanadi."
)

# GEMINI-3.6-FLASH BILAN SO'ROV YUBORISH
def generate_ai_content(prompt_text):
    full_prompt = (
        f"{prompt_text}\n\n"
        "Talablar: Telegram Markdown formatida, emojilar va aniq bo'limlar bilan, 2500 belgidan oshmasin. "
        "Oxirida '📚 Manba:' keltirilsin."
    )
    
    for attempt in range(3):
        try:
            response = ai_client.models.generate_content(
                model=CURRENT_AI_MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.4
                )
            )
            if response and response.text:
                return response.text.strip() + IMZO
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                time.sleep(2)
                continue
            else:
                raise e
    raise Exception("Sun'iy intellekt serverida yuklama mavjud. Birozdan so'ng qayta urinib ko'ring.")

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
    
    for attempt in range(3):
        try:
            response = ai_client.models.generate_content(
                model=CURRENT_AI_MODEL,
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
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                time.sleep(2)
                continue
            else:
                raise e
    raise Exception("Test tizimida yuklama mavjud.")

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

            # 08:30 — Tonggi motivatsiya va hikmat
            if current_time == "08:30" and not sent_flags["08:30"]:
                p = "Alisher Navoiy, Bobur yoki mumtoz allomalarimiz o'gitlaridan ilm, vaqt qadri va ustozlik haqida ibratli tonggi post yozing."
                matn = generate_ai_content(p)
                bot.send_message(CHANNEL_USERNAME, f"☀️ **KUN HIKMATI & TONGGI ILHOM**\n\n{matn}", parse_mode="Markdown")
                sent_flags["08:30"] = True

            # 13:00 — Kun so'zi (O'TIL yoki Etimologiya)
            elif current_time == "13:00" and not sent_flags["13:00"]:
                p = "O'zbek tilining izohli lug'ati yoki etimologik lug'at asosida bitta qiziqarli so'zning chuqur tahlilini (kun so'zi sifatida) taqdim eting."
                matn = generate_ai_content(p)
                bot.send_message(CHANNEL_USERNAME, f"📖 **KUN SO'ZI TAHLILI**\n\n{matn}", parse_mode="Markdown")
                sent_flags["13:00"] = True

            # 17:00 — Interfaol metodik mahorat
            elif current_time == "17:00" and not sent_flags["17:00"]:
                p = "Ona tili yoki adabiyot fanidan tasodifiy mavzuga zamonaviy interfaol metod ishlab chiqing. Mavzu, Metod nomi, Darsdagi o'rni, Qo'llash tartibi va Topsiriqni bering."
                matn = generate_ai_content(p)
                bot.send_message(CHANNEL_USERNAME, f"🎯 **METODIK MAHORAT RUKNI**\n\n{matn}", parse_mode="Markdown")
                sent_flags["17:00"] = True

            # 20:30 — 3 ta BMB Quiz testi
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
                        time.sleep(2)
                    except Exception:
                        pass
                sent_flags["20:30"] = True

            time.sleep(30)
        except Exception as e:
            print(f"Auto-posting xatosi: {e}")
            time.sleep(30)

threading.Thread(target=auto_poster_loop, daemon=True).start()

# --- MAXSUS BUYRUQ: ID ANIQLASH ---
@bot.message_handler(commands=['myid'])
def get_user_id(message):
    bot.reply_to(message, f"🆔 Sizning Telegram ID raqamingiz: `{message.from_user.id}`", parse_mode="Markdown")

# --- START VA OBUNA ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = (
        "╔════════════════════════╗\n"
        "  ✨ **AI TILSHUNOS & METODIST v4.1**\n"
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
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call):
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
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")

# --- ASOSIY MENYU VA BUYRUQLAR ---
@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = message.text

    if text == "🔙 Asosiy menyu":
        bot.send_message(message.chat.id, "Asosiy menyudasiz:", reply_markup=get_main_menu())
        return

    # 1. DARS ISHLANMASI (KONSPEKT)
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

    # 2. ESSE TEKSHIRUVI (50 BALLIK MEZON)
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

    # 3. ARUZ VAZNI TAHLILI
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

    # 4. QADIMGI VA ESKI TURKIY LEKSIKASI
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

    # 5. IMLO VA ORFOEPIYA
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

    # 6. INTERFAOL METODLAR
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

    # 7. G'AZAL TAHLILI
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

    # 8. O'TIL VA ETIMOLOGIYA
    elif text == "📖 So'z izohi (O'TIL)":
        msg = bot.reply_to(message, "📖 Izohli lug'at (O'TIL) bo'yicha tahlil qilish uchun so'zni yuboring:")
        p = "O'zbek tilining izohli lug'ati (O'TIL) asosida '{input}' so'zining to'liq leksik ma'nolari, uslubiy xoslanishi va matndan namunali gaplarni bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🔍 So'z etimologiyasi":
        msg = bot.reply_to(message, "🔍 Etimologiyasini bilmoqchi bo'lgan so'zingizni yuboring:")
        p = "Shavkat Rahmatullayevning 'O'zbek tilining etimologik lug'ati' asosida '{input}' so'zining tarixiy ildizi, o'zagi va ma'no taraqqiyotini tahlil qiling."
        bot.register_next_step_handler(msg, process_custom_step, p)

    # 9. BMB QUIZ TEST
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
            bot.reply_to(message, f"❌ Xatolik: {e}")

    else:
        bot.send_message(message.chat.id, "Iltimos, menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu())

print("AI Tilshunos v4.1 (gemini-3.6-flash) faol ishga tushdi...")
bot.infinity_polling()

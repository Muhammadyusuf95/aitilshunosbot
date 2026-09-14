import os
import threading
import json
import random
from flask import Flask
import telebot
from telebot import types as tele_types
from google import genai
from google.genai import types

# --- RENDER WEB SERVICE PORTI UCHUN SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Ona tili va Adabiyot ta'limiy boti faol ishlamoqda!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- SOZLAMALAR VA KALITLAR ---
TELEGRAM_TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@aitilshunos"  # Kanalingiz usernamesi

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

IMZO = (
    "\n\n────────────────\n"
    f"📚 **Kanalimiz:** {CHANNEL_USERNAME}\n"
    "🤖 **Bilimingizni sinash uchun bot:** @aitilshunosbot"
)

# --- MAJBURIY OBUNA TEKSHIRUVI ---
def is_subscribed(user_id):
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if chat_member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception:
        # Xatolik bo'lsa yoki bot kanalda admin bo'lmasa, to'xtab qolmasligi uchun True qaytaradi
        return True

def send_subscription_prompt(chat_id):
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    # Kanalga o'tish tugmasi
    btn_channel = tele_types.InlineKeyboardButton(
        text="📢 Kanalga a'zo bo'lish", 
        url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
    )
    # Tekshirish tugmasi
    btn_check = tele_types.InlineKeyboardButton(
        text="✅ A'zo bo'ldim / Tekshirish", 
        callback_data="check_sub"
    )
    markup.add(btn_channel, btn_check)

    matn = (
        "⚠️ **Botdan to'liq foydalanish uchun rasmiy kanalimizga a'zo bo'lishingiz lozim.**\n\n"
        f"Kanalimiz: {CHANNEL_USERNAME}\n\n"
        "A'zo bo'lgach, quyidagi **«A'zo bo'ldim / Tekshirish»** tugmasini bosing."
    )
    bot.send_message(chat_id, matn, parse_mode="Markdown", reply_markup=markup)

# --- GEMINI SISTEMA KO'RSATMASI ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi Xalq ta'limi tizimi va Bilim va malakalarni baholash agentligi (BMB/DTM) "
    "talablari asosida faoliyat yurituvchi nufuzli Ona tili va Adabiyot fani metodisti, leksikografi va ekspertisiz.\n\n"
    "ASOSIY STANDARTLAR:\n"
    "1. 5-11-sinf Ona tili va Adabiyot darsliklari.\n"
    "2. 5 jildli 'O'zbek tilining izohli lug'ati' (O'TIL) mezonlari.\n"
    "3. Shavkat Rahmatullayevning 'O'zbek tilining etimologik lug'ati'.\n"
    "4. Mumtoz adabiyot durdonalari poetikasi va badiiy san'atlari.\n"
    "5. Har bir post va test oxirida ANIQ MANBA ko'rsatilsin.\n\n"
    "QAT'IY TAQIQLAR:\n"
    "1. Siyosiy, diniy, huquqiy mavzular va davlat tuzumiga qarshi fikrlar butunlay man etiladi.\n"
    "2. Rahbariyat yoki davlat idoralarini tanqid qilish taqiqlanadi.\n"
    "3. Inson sha'ni va qadr-qimmatini kamsitishga yo'l qo'yilmaydi."
)

# --- GEMINI MATN TAYYORLASH FUNKSIYASI ---
def generate_ai_post(mavzu_turi="ilmiy"):
    mavzular = {
        "ilmiy": "5-11-sinf Ona tili darsliklari asosida qiyin grammatik qoidalar bo'yicha metodik post tayyorlang.",
        "adabiyot": "5-11-sinf Adabiyot darsliklaridagi durdona asarlar va qahramonlar tahlili haqida post tayyorlang.",
        "gazal": "Mumtoz adabiyotimizdan 1-2 bayt keltirib, badiiy san'atlari va ma'nosini sharhlovchi g'azal tahlili yozing.",
        "izoh": "O'zbek tilining izohli lug'ati (O'TIL) asosida darslikdagi 1 ta murakkab so'zning to'liq izohini tayyorlang.",
        "etimologiya": "O'zbek tilining etimologik lug'ati asosida 1 ta so'zning tarixiy kelib chiqishini tahlil qilib bering.",
        "esse": "Ona tili va adabiyotdan BMB mezonidagi 1 ta namunaviy esse rejasi va tezislari bilan post tuzing.",
        "fakt": "Darsliklar doirasidagi qiziqarli til hodisasi yoki adabiy fakt haqida post tayyorlang.",
        "motivatsiya": "Mumtoz adiblarimizdan ilm, mutolaa va kamolot haqida ibratli post yozing."
    }

    prompt = (
        f"{mavzular.get(mavzu_turi, mavzular['ilmiy'])}\n\n"
        "Talablar: Telegram Markdown formatida, emojilar bilan, oxirida '📚 Manba:' bo'lsin. "
        "Ortiqcha so'zsiz to'g'ridan-to'g'ri kanalga tayyor post bering."
    )

    response = ai_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.5
        )
    )
    return response.text.strip() + IMZO

def generate_ai_quiz():
    prompt = (
        "5-11-sinf Ona tili yoki Adabiyot darsliklari asosida BMB (DTM) standartida 4 variantli (A, B, C, D) "
        "1 ta Quiz test tuzing. Faqat quyidagi JSON formatida javob bering:\n"
        "{\n"
        '  "question": "Savol matni",\n'
        '  "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob izohi va darslik manbasi (200 belgidan oshmasin)"\n'
        "}\n"
        "correct_option_id 0, 1, 2 yoki 3 bo'lsin."
    )

    response = ai_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.4
        )
    )
    
    raw_text = response.text.strip()
    if "```json" in raw_text:
        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_text:
        raw_text = raw_text.split("```")[1].split("```")[0].strip()
        
    return json.loads(raw_text)

# --- BOT BUYRUQLARI (OBUNA TEKSHIRUVI BILAN) ---
def check_user_access(message):
    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return False
    return True

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not check_user_access(message):
        return

    matn = (
        "Assalomu alaykum! Ona tili va adabiyot ilmiy-ta'limiy botiga xush kelibsiz.\n\n"
        "Barcha materiallar darsliklar, O'TIL va etimologik lug'at asosida beriladi.\n\n"
        "📌 **Kanalga chiqarish buyruqlari:**\n"
        "📜 /gazal — Mumtoz g'azallar badiiy tahlili\n"
        "📖 /izoh — Izohli lug'at (O'TIL) asosida so'z sharhi\n"
        "🔍 /etimologiya — So'zlar etimologiyasi\n"
        "🔹 /post — Ona tili grammatikasi tahlili\n"
        "🔹 /adabiyot — Adabiy asarlar tahlili\n"
        "🔹 /esse — BMB namunaviy esse rejalari\n"
        "🔹 /fakt — Qiziqarli fanga oid faktlar\n"
        "🔹 /motivatsiya — Ilmiy-ma'rifiy motivatsiya\n"
        "🔹 /test — DTM mezonidagi Quiz testi"
    )
    bot.reply_to(message, matn)

# «A'zo bo'ldim / Tekshirish» tugmasi bosilganda:
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call):
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi! Xush kelibsiz.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_welcome(call.message)
    else:
        bot.answer_callback_query(
            call.id, 
            "❌ Siz hali kanalga a'zo bo'lmadingiz. Iltimos, avval kanalga obuna bo'ling!", 
            show_alert=True
        )

@bot.message_handler(commands=['gazal'])
def publish_gazal(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ Mumtoz g'azal tahlili tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="gazal")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ G'azal tahlili kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['izoh'])
def publish_izoh(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ O'TIL asosida so'z izohi tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="izoh")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ So'z izohi kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['etimologiya'])
def publish_etimologiya(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ Etimologik tahlil tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="etimologiya")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Etimologik tahlil kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['post'])
def publish_post(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ Grammatik post tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="ilmiy")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Post kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['adabiyot'])
def publish_adabiyot(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ Asar tahlili tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="adabiyot")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Adabiy post kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['esse'])
def publish_esse(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ Esse namunasi tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="esse")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Esse kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['fakt'])
def publish_fakt(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ Fakt tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="fakt")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Fakt kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['motivatsiya'])
def publish_motivatsiya(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ Motivatsion post tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="motivatsiya")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Motivatsiya kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['test'])
def publish_quiz(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ Quiz test tuzilmoqda...")
    try:
        quiz = generate_ai_quiz()
        bot.send_poll(
            chat_id=CHANNEL_USERNAME,
            question=quiz["question"],
            options=quiz["options"],
            type="quiz",
            correct_option_id=quiz["correct_option_id"],
            explanation=quiz.get("explanation", ""),
            is_anonymous=True
        )
        bot.reply_to(message, "✅ Quiz test kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

print("Majburiy a'zolik tizimiga ega bot ishga tushdi...")
bot.infinity_polling()

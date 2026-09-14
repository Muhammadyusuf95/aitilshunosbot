import os
import threading
import json
from flask import Flask
import telebot
from google import genai

# --- RENDER PORT TALABI UCHUN FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Gemini Pro ulanishi faol!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- SOZLAMALAR ---
TELEGRAM_TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"

# 1-bosqichda olgan kalitingizni bu yerga qo'ying:
# Kalitni to'g'ridan-to'g'ri yozmasdan, tizim o'zgaruvchisidan olamiz:
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@aitilshunos"  # Kanalingiz usernamesi

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

IMZO = (
    "\n\n────────────────\n"
    f"📚 **Kanalimiz:** {CHANNEL_USERNAME}\n"
    "🤖 **Bilimingizni sinash uchun bot:** @aitilshunosbot"
)

# --- GEMINI PRO ORQALI ILMIY POST YARATISH ---
def generate_ai_post():
    prompt = (
        "Siz o'zbek tili va adabiyoti bo'yicha yetuk mutaxassissiz. "
        "Telegram kanal uchun bitta chuqur ilmiy-ommabop, qiziqarli va mutlaqo yangi post yozib bering. "
        "Mavzular: mumtoz matnlar (Navoiy, Bobur va boshqalar), etnolingvistika, qadimiy so'zlar etimologiyasi "
        "yoki nutq madaniyati va imlo qoidalari bo'lsin. "
        "Post formati: chiroyli sarlavha, asosiy tahlil, xulosa va zarur emojilar (Telegram Markdown formatida). "
        "Ortiqcha kirish jumlalarisiz, to'g'ridan-to'g'ri post matnini bering."
    )
    response = ai_client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt
    )
    return response.text.strip() + IMZO

# --- GEMINI PRO ORQALI TEST (QUIZ) YARATISH ---
def generate_ai_quiz():
    prompt = (
        "Ona tili va o'zbek adabiyoti fani bo'yicha bitta murakkab va sifatli Quiz test tuzing. "
        "Javobni faqat va faqat quyidagi JSON formatida qaytaring, boshqa hech qanday izoh qo'shmang:\n"
        "{\n"
        '  "question": "Savol matni",\n'
        '  "options": ["Variant 1", "Variant 2", "Variant 3", "Variant 4"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob nega to\'g\'riligi haqida qisqa ilmiy izoh (200 belgidan oshmasin)"\n'
        "}\n"
        "correct_option_id qiymati 0, 1, 2 yoki 3 bo'lsin."
    )
    response = ai_client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt
    )
    raw_text = response.text.strip()
    if "```json" in raw_text:
        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_text:
        raw_text = raw_text.split("```")[1].split("```")[0].strip()
    return json.loads(raw_text)

# --- BUYRUQLAR ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        "Assalomu alaykum! AI Tilshunos (Gemini Pro) faol holatda.\n\n"
        "Buyruqlar:\n"
        "👉 /post — Gemini Pro ilmiy post yaratadi va kanalga chiqaradi\n"
        "👉 /test — Gemini Pro yangi Quiz test tuzadi va kanalga chiqaradi"
    )

@bot.message_handler(commands=['post'])
def publish_post(message):
    bot.reply_to(message, "⏳ Gemini Pro ilmiy post tayyorlamoqda...")
    try:
        matn = generate_ai_post()
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Post muvaffaqiyatli kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")

@bot.message_handler(commands=['test'])
def publish_quiz(message):
    bot.reply_to(message, "⏳ Gemini Pro Quiz test tuzmoqda...")
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
        bot.reply_to(message, "✅ Test muvaffaqiyatli kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")

print("Bot Gemini Pro bilan ishga tushdi...")
bot.infinity_polling()

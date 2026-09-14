import os
import threading
import random
from flask import Flask
import telebot

# --- RENDER PORT XATOSINI YOPISH UCHUN KICHIK SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 24/7 rejimda ishlamoqda!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Veb-serverni orqa fonda yoqamiz
threading.Thread(target=run_web, daemon=True).start()

# --- ASOSIY TELEGRAM BOT KODI ---
TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
bot = telebot.TeleBot(TOKEN)

CHANNEL_USERNAME = "@Onatilidanyordam"  # Kanalingiz nomi

POSTS = [
    (
        "📚 **Qiziqarli leksika: \"Arg‘uvon\" so‘zining ma’nosi**\n\n"
        "Mumtoz adabiyotimizda, xususan Alisher Navoiy va Bobur g‘azallarida "
        "«arg‘uvon» yoki «arg‘uvoniy» so‘zi ko‘p uchraydi.\n\n"
        "🌱 *Arg‘uvon* — bu bahorda to‘q qizil-binafsharang gul ochadigan manzarali buta/daraxtdir. "
        "Mumtoz she’riyatda bu so‘z ko‘pincha yorning qip-qizil labi, yuzi yoki oshiqning ko‘z yoshlariga "
        "tashbeh (o‘xshatish) sifatida qo‘llangan.\n\n"
        "📖 *\"Mayi arg‘uvoniy tut, ey dilrabo...\"*\n\n"
        "🔗 @onas — Ilm va ma'rifat ulashamiz!"
    ),
    (
        "💡 **Nutq madaniyati: To‘g‘ri talaffuz va imlo**\n\n"
        "Kundalik muloqotimizda tez-tez adashtiriladigan so‘zlar:\n\n"
        "❌ **Xato:** Xar hil, xursandchilik, mulohaza qilmoq\n"
        "✅ **To‘g‘ri:** Har xil, xursandlik, mulohaza yuritmoq\n\n"
        "📌 *Eslatma:* «Xursand» sifat bo‘lib, undan ot yasashda «-lik» qo‘shimchasi qo‘shiladi.\n\n"
        "🔗 @aitilshunos — Tilimiz sofligini asraylik!"
    )
]

QUIZZES = [
    {
        "question": "Alisher Navoiyning turkiy til himoyasiga bag‘ishlangan mashhur ilmiy asari qaysi?",
        "options": ["Majolis un-nafois", "Muhokamat ul-lug‘atayn", "Mezon ul-avzon", "Mahbub ul-qulub"],
        "correct_option_id": 1,
        "explanation": "«Muhokamat ul-lug‘atayn» asarida Navoiy turkiy tilning boy leksikasini arab va fors tillari bilan qiyoslab isbotlagan."
    },
    {
        "question": "Quyidagi so‘zlardan qaysi biri imlo qoidasiga ko‘ra to‘g‘ri yozilgan?",
        "options": ["Muhokoma", "Muvozanat", "Mubohasa", "Mukofat"],
        "correct_option_id": 1,
        "explanation": "To‘g‘ri shakli: 'Muvozanat'. Qolganlari: muhokama, mukofot."
    }
]

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        "Assalomu alaykum! AI Tilshunos botiga xush kelibsiz.\n\n"
        "Buyruqlar:\n"
        "👉 /post — Kanalga ilmiy post yuborish\n"
        "👉 /test — Kanalga Quiz test yuborish"
    )

@bot.message_handler(commands=['post'])
def publish_post(message):
    try:
        post = random.choice(POSTS)
        bot.send_message(CHANNEL_USERNAME, post, parse_mode="Markdown")
        bot.reply_to(message, "✅ Post muvaffaqiyatli kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

# Kanalga oddiy post chiqarish
@bot.message_handler(commands=['post'])
def publish_post(message):
    try:
        tanlangan_post = random.choice(POSTS)
        
        # Har bir post ostiga avtomatik qo'shiladigan imzo:
        imzo = (
            "\n\n────────────────\n"
            "📚 **Kanalimiz:** @aitilshunos\n"
            "🤖 **Bilimingizni sinash uchun bot:** @aitilshunosbot"
        )
        
        yakuniy_matn = tanlangan_post + imzo
        
        bot.send_message(CHANNEL_USERNAME, yakuniy_matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Post va havolalar kanalga muvaffaqiyatli chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

print("Bot muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()

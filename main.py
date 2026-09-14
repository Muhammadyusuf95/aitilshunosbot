import os
import threading
import json
import random
from flask import Flask
import telebot
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

# --- XAVFSIZLIK VA ASOSIY SOZLAMALAR ---
TELEGRAM_TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
# Kalit Render Environment'dan olinadi:
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@aitilshunos"  # Kanalingiz usernamesi

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

IMZO = (
    "\n\n────────────────\n"
    f"📚 **Kanalimiz:** {CHANNEL_USERNAME}\n"
    "🤖 **Bilimingizni sinash uchun bot:** @aitilshunosbot"
)

# --- QAT'IY ILMIY, PEDAGOGIK VA QONUNIY TIZIMLI KO'RSATMA ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi Xalq ta'limi tizimi va Bilim va malakalarni baholash agentligi (BMB/DTM) "
    "talablari asosida faoliyat yurituvchi nufuzli Ona tili va Adabiyot fani metodisti va ekspertisiz.\n\n"
    "ASOSIY VAZIFA:\n"
    "- O'qituvchilar, maktab o'quvchilari va abituriyentlar uchun faqat tasdiqlangan 5-11-sinf Ona tili va Adabiyot "
    "darsliklari hamda darslikdagi mumtoz/zamonaviy badiiy asarlar asosida ilmiy-metodik materiallar, tahlillar, "
    "esse rejalari, imlo qoidalari, BMB testlari va motivatsion fikrlar tayyorlash.\n"
    "- Har bir post, fakt va test oxirida ANIQ MANBA ko'rsatilishi shart (Masalan: '📚 Manba: 9-sinf Adabiyot darsligi, 1-qism' yoki '📚 Manba: 7-sinf Ona tili').\n\n"
    "QAT'IY QONUNIY VA AXLOQIY CHEKLOVLAR (BU CHEKLOVLARNI BUZISH MUTLAQO TAQIQLANADI):\n"
    "1. O'zbekiston Respublikasining davlat tuzumi, suvereniteti, mustaqilligi va amaldagi qonunchiligiga zid har qanday fikr qat'iyan man etiladi.\n"
    "2. Amaldagi davlat rahbariyati, davlat siyosati va davlat organlari faoliyatini tanqid qilish yoki muhokama qilish qat'iyan taqiqlanadi.\n"
    "3. Diniy, siyosiy, huquqiy va ijtimoiy-bahsli mavzularga umuman daxl qilinmasin.\n"
    "4. Hech qanday shaxsning sha'ni, qadr-qimmati kamsitilmasin, millatlararo, mintaqaviy yoki ijtimoiy nizo keltirib chiqaruvchi jumlalar ishlatilmasin.\n"
    "5. Matnlar faqat sof, adabiy o'zbek tili (lotin alifbosida), yuksak pedagogik madaniyat va ilmiy etika bilan yozilishi shart."
)

# --- GEMINI 3.6 FLASH ORQALI ILMIY MATERIALLAR TAYYORLASH ---
def generate_ai_post(mavzu_turi="ilmiy"):
    mavzular = {
        "ilmiy": (
            "5-11-sinf Ona tili darsliklari asosida o'qituvchi va abituriyentlar uchun qiyin yoki nozik grammatik qoidalar, "
            "sintaktik tahlil, morfemika yoki tinish belgilari me'yorlari bo'yicha ilmiy-metodik post tayyorlang."
        ),
        "adabiyot": (
            "5-11-sinf Adabiyot darsliklariga kiritilgan asarlar (mumtoz yoki o'zbek adabiyoti durdonalari) tahlili, "
            "badiiy san'atlar, qahramonlar xarakteri yoki darslik doirasidagi adiblar ijodi haqida tahliliy post tayyorlang."
        ),
        "esse": (
            "Ona tili va adabiyot darsliklari asosida o'quvchi va abituriyentlar uchun BMB talablariga mos bitta "
            "namunaviy esse/insho mavzusi, uning puxta rejasi, asosiy dalillari va xulosasi berilgan metodik post tayyorlang."
        ),
        "fakt": (
            "Maktab ona tili va adabiyot darsliklari doirasida o'quvchilar kam e'tibor beradigan qiziqarli etimologik "
            "hodisalar, qadimiy so'zlar ma'nosi yoki asarlardagi qiziqarli ilmiy faktlar haqida post tayyorlang."
        ),
        "motivatsiya": (
            "Darsliklarimizdagi ulug' mutafakkirlar (Alisher Navoiy, Mirzo Bobur, Abdulla Qodiriy, Cho'lpon, Abdulla Oripov va b.) "
            "asarlaridagi ilm olish, mehnatsevarlik, kitobxonlik va kamolot haqidagi fikrlari asosida o'quvchilar uchun ibratli post yozing."
        )
    }

    prompt = (
        f"{mavzular.get(mavzu_turi, mavzular['ilmiy'])}\n\n"
        "Talablar:\n"
        "- Matnni chiroyli sarlavhalar, xatboshilar va mos emojilar bilan Markdown formatida bezating.\n"
        "- Post so'ngida aniq manbani (darslik sinfi va fani) ko'rsating.\n"
        "- Hech qanday siyosiy, diniy, huquqiy yoki noo'rin mavzularga tegmang.\n"
        "- Ortiqcha kirish so'zlarsiz, to'g'ridan-to'g'ri kanalga chiqarishga tayyor matn bering."
    )

    response = ai_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.6
        )
    )
    return response.text.strip() + IMZO

# --- GEMINI 3.6 FLASH ORQALI BMB MEZONIDAGI TEST TUZISH ---
def generate_ai_quiz():
    prompt = (
        "5-11-sinf Ona tili yoki Adabiyot darsliklari asosida BMB (DTM) davlat testlari standartlariga to'liq mos, "
        "mantiqiy va sifatli 4 variantli (A, B, C, D) 1 ta Quiz test tuzing.\n"
        "Faqat va faqat quyidagi JSON formatida javob bering, hech qanday qo'shimcha matnsiz:\n"
        "{\n"
        '  "question": "Savol matni (darslikdagi qoida, she\'riy san\'at yoki asar yuzasidan)",\n'
        '  "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob nega to\'g\'riligi va aynan qaysi sinf darsligidan olingani haqida izoh (200 belgidan oshmasin)"\n'
        "}\n"
        "correct_option_id faqat to'g'ri javobning indeksi bo'lsin: 0, 1, 2 yoki 3."
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

# --- BOT BUYRUQLARI ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    matn = (
        "Assalomu alaykum! Ona tili va adabiyot fani bo'yicha maxsus ta'limiy bot faoliyat yuritmoqda.\n\n"
        "Barcha materiallar tasdiqlangan maktab darsliklari asosida rasmiy manbasi bilan taqdim etiladi.\n\n"
        "📌 **Kanalga kontent chiqarish buyruqlari:**\n"
        "🔹 /post — Grammatika va metodikaga oid darslik tahlillari\n"
        "🔹 /adabiyot — Adabiy asarlar va badiiy tahlillar\n"
        "🔹 /esse — BMB talablari asosidagi esse/insho reja va namunalari\n"
        "🔹 /fakt — Darsliklardagi qiziqarli etimologik faktlar\n"
        "🔹 /motivatsiya — Mumtoz adiblardan ilm va kitobxonlik ibratlari\n"
        "🔹 /test — Darsliklar asosidagi BMB Quiz testi\n"
        "🔹 /random — Tasodifiy bitta foydali material chiqarish"
    )
    bot.reply_to(message, matn)

@bot.message_handler(commands=['post'])
def publish_post(message):
    bot.reply_to(message, "⏳ Darsliklar asosida ilmiy-metodik post tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="ilmiy")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Ilmiy post kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['adabiyot'])
def publish_adabiyot(message):
    bot.reply_to(message, "⏳ Adabiyot darsliklari asosida tahlil tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="adabiyot")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Adabiyot bo'yicha post kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['esse'])
def publish_esse(message):
    bot.reply_to(message, "⏳ Darslik mezonlari asosida esse tahlili tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="esse")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Esse materiali kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['fakt'])
def publish_fakt(message):
    bot.reply_to(message, "⏳ Fanga oid qiziqarli fakt tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="fakt")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Qiziqarli fakt kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['motivatsiya'])
def publish_motivatsiya(message):
    bot.reply_to(message, "⏳ Ilmiy motivatsiya tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="motivatsiya")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Motivatsion post kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['test'])
def publish_quiz(message):
    bot.reply_to(message, "⏳ Darslikka tayangan BMB Quiz testi tuzilmoqda...")
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
        bot.reply_to(message, "✅ Quiz test kanalga muvaffaqiyatli chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['random'])
def publish_random(message):
    tanlov = random.choice(["post", "adabiyot", "esse", "fakt", "motivatsiya", "test"])
    if tanlov == "test":
        publish_quiz(message)
    elif tanlov == "adabiyot":
        publish_adabiyot(message)
    elif tanlov == "esse":
        publish_esse(message)
    elif tanlov == "fakt":
        publish_fakt(message)
    elif tanlov == "motivatsiya":
        publish_motivatsiya(message)
    else:
        publish_post(message)

print("Xavfsiz va sertifikatlangan ta'limiy bot ishga tushdi...")
bot.infinity_polling()

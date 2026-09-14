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
    "talablari asosida faoliyat yurituvchi nufuzli Ona tili va Adabiyot fani metodisti, leksikografi va ekspertisiz.\n\n"
    "ASOSIY ILMIY MANBALAR VA STANDARTLAR:\n"
    "1. 5-11-sinf Ona tili va Adabiyot darsliklari (davlat ta'lim standartlari doirasida).\n"
    "2. 5 jildli 'O'zbek tilining izohli lug'ati' (O'TIL) mezonlari.\n"
    "3. Shavkat Rahmatullayevning 'O'zbek tilining etimologik lug'ati' (turkiy, arabiy, forsiy-tojikiy asoslar).\n"
    "4. Mumtoz adabiyot (Alisher Navoiy, Mirzo Bobur, Ogahiy, Fuzuliy) asarlari poetikasi va badiiy san'atlari.\n"
    "5. Har bir post, lug'aviy tahlil, etimologik izoh va test oxirida ANIQ MANBA ko'rsatilsin "
    "(Masalan: '📚 Manba: O'zbek tilining izohli lug'ati, II jild' yoki '📚 Manba: 9-sinf Adabiyot, G'azal tahlili').\n\n"
    "QAT'IY QONUNIY VA AXLOQIY CHEKLOVLAR (BU CHEKLOVLARNI BUZISH MUTLAQO TAQIQLANADI):\n"
    "1. O'zbekiston Respublikasining davlat tuzumi, suvereniteti, mustaqilligi va amaldagi qonunchiligiga zid har qanday fikr qat'iyan man etiladi.\n"
    "2. Amaldagi davlat rahbariyati, davlat siyosati va davlat organlari faoliyatini tanqid qilish yoki muhokama qilish qat'iyan taqiqlanadi.\n"
    "3. Diniy, siyosiy, huquqiy va ijtimoiy-bahsli mavzularga umuman daxl qilinmasin.\n"
    "4. Hech qanday shaxsning sha'ni, qadr-qimmati kamsitilmasin, nizo keltirib chiqaruvchi jumlalar ishlatilmasin.\n"
    "5. Matnlar faqat sof, mukammal adabiy o'zbek tilida (lotin alifbosida), yuksak filologik madaniyat bilan taqdim etilsin."
)

# --- GEMINI ORQALI POSTLAR YARATISH ---
def generate_ai_post(mavzu_turi="ilmiy"):
    mavzular = {
        "ilmiy": (
            "5-11-sinf Ona tili darsliklari asosida o'qituvchi va abituriyentlar uchun qiyin yoki nozik grammatik qoidalar, "
            "morfemika, sintaktik aloqalar yoki imlo me'yorlari bo'yicha ilmiy-metodik post tayyorlang."
        ),
        "adabiyot": (
            "5-11-sinf Adabiyot darsliklaridagi mumtoz yoki zamonaviy durdona asarlar tahlili, "
            "obrazlar tizimi va adiblar mahorati haqida tahliliy post tayyorlang."
        ),
        "gazal": (
            "Mumtoz adabiyotimiz durdonalaridan (Alisher Navoiy, Zahiriddin Muhammad Bobur, Lutfiy yoki Ogahiy) "
            "1-2 bayt g'azal matnini keltirib, uning g'oyaviy-falsafiy ma'nosi, qo'llangan badiiy san'atlari "
            "(tazod, tanosub, iytilof, tashbeh, istiora va b.) hamda darslikdagi ahamiyati bo'yicha yuksak darajadagi "
            "badiiy-ilmiy tahlil tayyorlang. Baytdagi qiyin so'zlar sharhini ham bering."
        ),
        "izoh": (
            "O'zbek tilining izohli lug'ati (5 jildlik) asosida darsliklarimizda va mumtoz matnlarda uchraydigan "
            "1 yoki 2 ta ko'p ma'noli, faol yoki eskirgan (arxaik/tarixiy) so'zning lug'aviy izohini tayyorlang. "
            "So'zning to'g'ri va ko'chma ma'nolari, uslubiy xoslanishi va darslikdagi badiiy asarlardan namunali jumlalar keltirilsin."
        ),
        "etimologiya": (
            "Shavkat Rahmatullayevning 'O'zbek tilining etimologik lug'ati' asosida o'zbek tilidagi qiziqarli "
            "1-2 ta so'zning kelib chiqish tarixini tahlil qiling. So'zning qadimgi turkiy, arabiy yoki forsiy ildizi, "
            "birlamchi tovush o'zgarishlari va tarixiy ma'nosi qanday o'zgarganini aniq va ilmiy-ommabop tilda yoritib bering."
        ),
        "esse": (
            "Ona tili va adabiyot darsliklari asosida BMB talablariga mos bitta namunaviy esse mavzusi, "
            "uning mukammal rejasi, asosiy tezislari va adabiy dalillari berilgan metodik tavsiya tayyorlang."
        ),
        "fakt": (
            "Darsliklarimiz doirasida o'quvchi va abituriyentlar kam e'tibor beradigan qiziqarli til hodisasi, "
            "etnolingvistik jihat yoki mumtoz asarlarga oid qiziqarli ilmiy fakt haqida post tayyorlang."
        ),
        "motivatsiya": (
            "Alisher Navoiy, Bobur, Abdulla Qodiriy kabi buyuk ajdodlarimizning ilm-ma'rifat, vaqt qadri, "
            "kitob mutolaasi va tilni e'zozlash haqidagi ibratli fikrlari asosida motivatsion post tayyorlang."
        )
    }

    prompt = (
        f"{mavzular.get(mavzu_turi, mavzular['ilmiy'])}\n\n"
        "Talablar:\n"
        "- Matnni chiroyli sarlavhalar, bo'limlar va mos emojilar bilan Telegram Markdown formatida tuzing.\n"
        "- Post so'ngida aniq manbani ('📚 Manba:' ko'rinishida) ko'rsating.\n"
        "- Siyosiy, diniy, huquqiy va davlatga zid mavzularga aslo yaqinlashmang.\n"
        "- To'g'ridan-to'g'ri kanalga chiqarishga tayyor, sifatli matn taqdim eting."
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

# --- GEMINI ORQALI BMB QUIZ TESTI ---
def generate_ai_quiz():
    prompt = (
        "5-11-sinf Ona tili yoki Adabiyot darsliklari (shu jumladan O'TIL, she'riy san'atlar yoki asarlar) asosida "
        "BMB (DTM) davlat imtihonlari darajasidagi 4 variantli (A, B, C, D) 1 ta murakkab va mantiqiy Quiz test tuzing.\n"
        "Faqat va faqat quyidagi JSON formatida javob bering:\n"
        "{\n"
        '  "question": "Savol matni (bayt tahlili, qoida, so\'z ma\'nosi yoki badiiy san\'at yuzasidan)",\n'
        '  "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob izohi va aniq manba (darslik yoki lug\'at nomi, 200 belgidan oshmasin)"\n'
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
        "Assalomu alaykum! Ona tili va adabiyot ilmiy-ta'limiy botiga xush kelibsiz.\n\n"
        "Barcha materiallar darsliklar, O'zbek tilining izohli hamda etimologik lug'atlari asosida tayyorlanadi.\n\n"
        "📌 **Kanalga chiqarish buyruqlari:**\n"
        "📜 /gazal — Mumtoz g'azallar va baytlar badiiy tahlili\n"
        "📖 /izoh — Izohli lug'at asosida so'zlar sharhi (O'TIL)\n"
        "🔍 /etimologiya — So'zlar tarixi va etimologik tahlili\n"
        "🔹 /post — Grammatika va til qoidalari metodikasi\n"
        "🔹 /adabiyot — Darslikdagi adabiy asarlar tahlili\n"
        "🔹 /esse — BMB talabidagi esse/insho rejalari\n"
        "🔹 /fakt — Fanga oid qiziqarli darslik faktlari\n"
        "🔹 /motivatsiya — Mumtoz adiblardan ibratli fikrlar\n"
        "🔹 /test — DTM/BMB mezonidagi Quiz testi\n"
        "🎲 /random — Yuqoridagilardan birini tasodifiy chiqarish"
    )
    bot.reply_to(message, matn)

@bot.message_handler(commands=['gazal'])
def publish_gazal(message):
    bot.reply_to(message, "⏳ Mumtoz g'azal va bayt tahlili tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="gazal")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ G'azal tahlili kanalga muvaffaqiyatli chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['izoh'])
def publish_izoh(message):
    bot.reply_to(message, "⏳ Izohli lug'at (O'TIL) asosida so'z sharhi tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="izoh")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ So'z izohi kanalga muvaffaqiyatli chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['etimologiya'])
def publish_etimologiya(message):
    bot.reply_to(message, "⏳ Etimologik lug'at asosida so'z tarixi tahlil qilinmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="etimologiya")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Etimologik tahlil kanalga muvaffaqiyatli chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['post'])
def publish_post(message):
    bot.reply_to(message, "⏳ Darsliklar asosida ilmiy post tayyorlanmoqda...")
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
        bot.reply_to(message, "✅ Adabiy post kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['esse'])
def publish_esse(message):
    bot.reply_to(message, "⏳ Esse reja va tahlili tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="esse")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Esse materiali kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['fakt'])
def publish_fakt(message):
    bot.reply_to(message, "⏳ Qiziqarli fakt tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="fakt")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Fakt kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['motivatsiya'])
def publish_motivatsiya(message):
    bot.reply_to(message, "⏳ Motivatsion post tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="motivatsiya")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Motivatsiya kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['test'])
def publish_quiz(message):
    bot.reply_to(message, "⏳ BMB Quiz testi tuzilmoqda...")
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

@bot.message_handler(commands=['random'])
def publish_random(message):
    tanlov = random.choice([
        "gazal", "izoh", "etimologiya", "post", 
        "adabiyot", "esse", "fakt", "motivatsiya", "test"
    ])
    if tanlov == "test":
        publish_quiz(message)
    else:
        bot.reply_to(message, f"⏳ Tasodifiy tanlov bo'yicha '{tanlov}' tayyorlanmoqda...")
        try:
            matn = generate_ai_post(mavzu_turi=tanlov)
            bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
            bot.reply_to(message, f"✅ '{tanlov}' bo'limi kanalga chiqdi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

print("Akademik tilshunoslik va adabiyot boti faol ishga tushdi...")
bot.infinity_polling()

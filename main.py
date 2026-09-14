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

# Kanalingiz manzili yangilandi:
CHANNEL_USERNAME = "@onatilidanyordam"

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
        # Xatolik bo'lsa yoki admin ruxsati kechiksa, to'xtab qolmasligi uchun
        return True

def send_subscription_prompt(chat_id):
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    btn_channel = tele_types.InlineKeyboardButton(
        text="📢 Kanalga a'zo bo'lish", 
        url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
    )
    btn_check = tele_types.InlineKeyboardButton(
        text="✅ A'zo bo'ldim / Tekshirish", 
        callback_data="check_sub"
    )
    markup.add(btn_channel, btn_check)

    matn = (
        "⚠️ **Botdan foydalanish uchun rasmiy kanalimizga a'zo bo'lishingiz lozim.**\n\n"
        f"Kanalimiz: {CHANNEL_USERNAME}\n\n"
        "A'zo bo'lgach, quyidagi **«A'zo bo'ldim / Tekshirish»** tugmasini bosing."
    )
    bot.send_message(chat_id, matn, parse_mode="Markdown", reply_markup=markup)

# --- GEMINI SISTEMA KO'RSATMASI (MAKTAB DARSLIKLARI VA ILMIY STANDARTLAR) ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi Xalq ta'limi tizimi va Bilim va malakalarni baholash agentligi (BMB/DTM) "
    "talablari asosida faoliyat yurituvchi nufuzli Ona tili va Adabiyot fani metodisti, leksikografi va ekspertisiz.\n\n"
    "ASOSIY STANDARTLAR:\n"
    "1. 5-11-sinf Ona tili va Adabiyot darsliklari (davlat ta'lim standartlari doirasida).\n"
    "2. 5 jildli 'O'zbek tilining izohli lug'ati' (O'TIL) mezonlari.\n"
    "3. Shavkat Rahmatullayevning 'O'zbek tilining etimologik lug'ati'.\n"
    "4. Mumtoz adabiyot durdonalari poetikasi va badiiy san'atlari.\n"
    "5. Har bir post, lug'aviy tahlil, etimologik izoh va test oxirida ANIQ MANBA ko'rsatilsin.\n\n"
    "QAT'IY QONUNIY VA AXLOQIY CHEKLOVLAR (BU CHEKLOVLARNI BUZISH MUTLAQO TAQIQLANADI):\n"
    "1. O'zbekiston Respublikasining davlat tuzumi, suvereniteti, mustaqilligi va amaldagi qonunchiligiga zid fikrlar man etiladi.\n"
    "2. Davlat rahbariyati, davlat siyosati va davlat organlari faoliyatini tanqid qilish taqiqlanadi.\n"
    "3. Diniy, siyosiy, huquqiy va ijtimoiy-bahsli mavzularga umuman daxl qilinmasin.\n"
    "4. Hech qanday shaxsning sha'ni, qadr-qimmati kamsitilmasin.\n"
    "5. Matnlar faqat sof, mukammal adabiy o'zbek tilida (lotin alifbosida), yuksak pedagogik madaniyat bilan taqdim etilsin."
)

# --- GEMINI MATN TAYYORLASH FUNKSIYASI ---
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
            "Mumtoz adabiyotimiz durdonalaridan (Navoiy, Bobur, Lutfiy, Ogahiy) 1-2 bayt keltirib, "
            "uning g'oyaviy-falsafiy ma'nosi, badiiy san'atlari (tazod, tanosub, istiora va b.) va darslikdagi "
            "ahamiyati bo'yicha yuksak darajadagi badiiy-ilmiy tahlil yozing. Qiyin so'zlar sharhini ham bering."
        ),
        "izoh": (
            "O'zbek tilining izohli lug'ati (5 jildlik) asosida darsliklarimizda va mumtoz matnlarda uchraydigan "
            "1 yoki 2 ta murakkab so'zning lug'aviy izohini tayyorlang. So'zning ma'nolari, uslubiy xoslanishi va namunaviy gaplar keltiring."
        ),
        "etimologiya": (
            "Shavkat Rahmatullayevning 'O'zbek tilining etimologik lug'ati' asosida o'zbek tilidagi qiziqarli "
            "1-2 ta so'zning kelib chiqish tarixini tahlil qiling. Birlamchi ildiz va tovush o'zgarishlarini ilmiy-ommabop tushuntiring."
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
            "Alisher Navoiy, Mirzo Bobur, Abdulla Qodiriy kabi buyuk ajdodlarimizning ilm olish, kitobxonlik va "
            "tilni e'zozlash haqidagi ibratli fikrlari asosida motivatsion post yozing."
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

# --- GEMINI QUIZ TEST TUZISH ---
def generate_ai_quiz():
    prompt = (
        "5-11-sinf Ona tili yoki Adabiyot darsliklari (shu jumladan O'TIL, she'riy san'atlar yoki asarlar) asosida "
        "BMB (DTM) davlat imtihonlari darajasidagi 4 variantli (A, B, C, D) 1 ta murakkab va mantiqiy Quiz test tuzing.\n"
        "Faqat va faqat quyidagi JSON formatida javob bering:\n"
        "{\n"
        '  "question": "Savol matni",\n'
        '  "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob izohi va aniq darslik manbasi (200 belgidan oshmasin)"\n'
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
        "Barcha materiallar darsliklar, O'zbek tilining izohli hamda etimologik lug'atlari asosida taqdim etiladi.\n\n"
        "📌 **Kanalga chiqarish buyruqlari:**\n"
        "📜 /gazal — Mumtoz g'azallar va baytlar badiiy tahlili\n"
        "📖 /izoh — Izohli lug'at asosida so'zlar sharhi (O'TIL)\n"
        "🔍 /etimologiya — So'zlar tarixi va etimologik tahlili\n"
        "🔹 /post — Ona tili grammatikasi va qoidalar metodikasi\n"
        "🔹 /adabiyot — Darslikdagi adabiy asarlar tahlili\n"
        "🔹 /esse — BMB talabidagi esse/insho rejalari\n"
        "🔹 /fakt — Fanga oid qiziqarli darslik faktlari\n"
        "🔹 /motivatsiya — Mumtoz adiblardan ilm haqida ibratli fikrlar\n"
        "🔹 /test — DTM/BMB mezonidagi Quiz testi\n"
        "🎲 /random — Yuqoridagilardan birini tasodifiy chiqarish"
    )
    bot.reply_to(message, matn)

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
        bot.reply_to(message, "✅ G'azal tahlili kanalga muvaffaqiyatli chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['izoh'])
def publish_izoh(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ O'TIL asosida so'z izohi tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="izoh")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ So'z izohi kanalga muvaffaqiyatli chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

@bot.message_handler(commands=['etimologiya'])
def publish_etimologiya(message):
    if not check_user_access(message): return
    bot.reply_to(message, "⏳ Etimologik tahlil tayyorlanmoqda...")
    try:
        matn = generate_ai_post(mavzu_turi="etimologiya")
        bot.send_message(CHANNEL_USERNAME, matn, parse_mode="Markdown")
        bot.reply_to(message, "✅ Etimologik tahlil kanalga muvaffaqiyatli chiqdi!")
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

@bot.message_handler(commands=['random'])
def publish_random(message):
    if not check_user_access(message): return
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

print("Kanal yangilandi (@onatilidanyordam). Bot faol ishlamoqda...")
bot.infinity_polling()

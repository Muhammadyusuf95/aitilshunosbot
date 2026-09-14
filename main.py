import os
import threading
import json
import random
from flask import Flask
import telebot
from telebot import types as tele_types
from google import genai
from google.genai import types

# --- RENDER UCHUN FLASK VEB SERVERI ---
app = Flask(__name__)

@app.route('/')
def home():
    return "AI Tilshunos & Metodist boti faol ishlamoqda!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- SOZLAMALAR VA KALITLAR ---
TELEGRAM_TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@onatilidanyordam"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

IMZO = (
    "\n\n────────────────\n"
    f"🌟 **Rasmiy kanal:** {CHANNEL_USERNAME}\n"
    "✨ **Pedagogik & Ilmiy bot:** @aitilshunosbot"
)

# --- REPLAY ASOSIY MENYU TUGMALARI ---
def get_main_menu():
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_method = tele_types.KeyboardButton("🎯 Interfaol metod")
    btn_gazal = tele_types.KeyboardButton("📜 G'azal tahlili")
    btn_izoh = tele_types.KeyboardButton("📖 So'z izohi (O'TIL)")
    btn_etimologiya = tele_types.KeyboardButton("🔍 Etimologiya")
    btn_post = tele_types.KeyboardButton("📝 Grammatika")
    btn_adabiyot = tele_types.KeyboardButton("📚 Adabiyot tahlili")
    btn_esse = tele_types.KeyboardButton("✍️ Namunaviy esse")
    btn_test = tele_types.KeyboardButton("🧠 BMB Quiz Test")
    btn_random = tele_types.KeyboardButton("🎲 Tasodifiy gavhar")
    
    markup.add(btn_method)
    markup.add(btn_gazal, btn_izoh)
    markup.add(btn_etimologiya, btn_post)
    markup.add(btn_adabiyot, btn_esse)
    markup.add(btn_test, btn_random)
    return markup

# --- KANALGA XAVFSIZ POST YUBORISH ---
def safe_send_to_channel(text):
    if len(text) > 3900:
        text = text[:3900] + "...\n*(Davomi qisqartirildi)*"
    try:
        bot.send_message(CHANNEL_USERNAME, text, parse_mode="Markdown")
    except Exception:
        bot.send_message(CHANNEL_USERNAME, text)

# --- MAJBURIY OBUNA TEKSHIRUVI ---
def is_subscribed(user_id):
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if chat_member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception:
        return True

def send_subscription_prompt(chat_id):
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    btn_channel = tele_types.InlineKeyboardButton(
        text="✨ Kanalga obuna bo'lish", 
        url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
    )
    btn_check = tele_types.InlineKeyboardButton(
        text="🔄 Obunani tekshirish", 
        callback_data="check_sub"
    )
    markup.add(btn_channel, btn_check)

    matn = (
        "╔════════════════════════╗\n"
        "   🏛 **AI TILSHUNOS METODIK MARKAZI**\n"
        "╚════════════════════════╝\n\n"
        "Assalomu alaykum, aziz ustoz va qadrli talaba!\n\n"
        f"Botdan to'liq foydalanish uchun **{CHANNEL_USERNAME}** kanaliga obuna bo'lishingiz lozim.\n\n"
        "Obuna bo'lgach, pastdagi **«Obunani tekshirish»** tugmasini bosing:"
    )
    bot.send_message(chat_id, matn, parse_mode="Markdown", reply_markup=markup)

# --- GEMINI QOIDALARI VA MEZONLARI ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi umumta'lim maktablari Ona tili va adabiyoti fani bo'yicha "
    "tajribali metodist, tilshunos va pedagogik ekspertisiz.\n"
    "1. Darsliklar, O'zbek tilining izohli lug'ati (O'TIL) hamda Shavkat Rahmatullayevning "
    "etimologik lug'ati standartlariga qat'iy tayaning.\n"
    "2. Har bir ma'lumot va metodik tavsiya oxirida aniq darslik yoki lug'at manbasini ko'rsating.\n"
    "3. Siyosiy, diniy, davlatga zid yoki shaxs sha'niga tegadigan mavzularga aslo yaqinlashmang.\n"
    "4. Faqat sof, lotin yozuvidagi adabiy tilda javob bering."
)

# --- GEMINI MATN YARATISH ---
def generate_ai_post(mavzu_turi="metod"):
    mavzular = {
        "metod": (
            "Ona tili yoki Adabiyot fanidan muayyan dars mavzusi bo'yicha (sinf ko'rsatilishi shart emas) "
            "darsda o'quvchilarni faollashtiruvchi zamonaviy 1 ta interfaol metod ishlab chiqing.\n"
            "Format:\n"
            "📌 **Mavzu:** [Mavzu nomi]\n"
            "🎯 **Metod nomi:** [Masalan: FSMU, Sinkveyn, Zinama-zina, Klaster va b.]\n"
            "⏳ **Darsdagi o'rni:** [Yangi mavzuda / Mustahkamlashda]\n"
            "🛠 **Qo'llash tartibi:** [Bosqichma-bosqich yo'riqnoma]\n"
            "💡 **Darslikdan namunaviy misol/topshiriq:** [Amaliy matn]\n"
            "✨ **Pedagogik natija:** [Qisqa xulosa]"
        ),
        "gazal": "Mumtoz adabiyotimizdan (Navoiy, Bobur, Ogahiy) 1-2 bayt keltirib, badiiy san'atlari va so'zlar sharhini beruvchi g'azal tahlili yozing.",
        "izoh": "O'zbek tilining izohli lug'ati (O'TIL) asosida 1-2 ta so'zning to'liq ma'nolari va namunali badiiy gaplar bilan izohini bering.",
        "etimologiya": "O'zbek tilining etimologik lug'ati asosida 1-2 ta so'zning tarixiy ildizi va tovush o'zgarishlarini tushuntiring.",
        "ilmiy": "Ona tili darsliklari bo'yicha murakkab grammatik qoida tahlilini metodik tarzda yoritib bering.",
        "adabiyot": "Adabiyot darsliklaridagi sara asarlar tahlili va qahramonlar xarakteri haqida post tayyorlang.",
        "esse": "BMB mezonlariga mos bitta namunaviy esse rejasi, asosiy tezislari va adabiy dalillarini bering.",
        "fakt": "Darsliklarimiz bo'yicha qiziqarli tilshunoslik yoki adabiyot faktini yozing.",
        "motivatsiya": "Ajdodlarimiz o'gitlari asosida ilm va mutolaaga undovchi ibratli post yozing."
    }

    prompt = (
        f"{mavzular.get(mavzu_turi, mavzular['metod'])}\n\n"
        "TALABLAR: Matn ixcham bo'lsin (2000 belgidan oshmasin), chiroyli sarlavhalar va emojilar bo'lsin. "
        "Oxirida '📚 Manba:' yozilsin. Ortiqcha so'zlarsiz to'g'ridan-to'g'ri kanalga chiqarishga tayyor holda bering."
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
        "Ona tili yoki Adabiyot fanidan BMB (DTM) standartida 4 variantli (A, B, C, D) 1 ta Quiz test tuzing. "
        "Faqat quyidagi JSON formatida javob bering:\n"
        "{\n"
        '  "question": "Savol matni",\n'
        '  "options": ["A varianti", "B varianti", "C varianti", "D varianti"],\n'
        '  "correct_option_id": 0,\n'
        '  "explanation": "To\'g\'ri javob tahlili va darslik manbasi (180 belgidan oshmasin)"\n'
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
        "╔════════════════════════╗\n"
        "  📚 **AI TILSHUNOS & METODIST BOT**\n"
        "╚════════════════════════╝\n\n"
        "Assalomu alaykum, aziz ustoz va bilimga chanqoq yoshlar!\n\n"
        "Kerakli bo'limni tanlash uchun pastdagi tugmalardan foydalaning:"
    )
    bot.send_message(message.chat.id, matn, parse_mode="Markdown", reply_markup=get_main_menu())

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
        bot.answer_callback_query(
            call.id, 
            "❌ Siz hali kanalga a'zo bo'lmadingiz. Iltimos, kanalga obuna bo'ling!", 
            show_alert=True
        )

# --- TUGMALARNI QAYTA ISHLASH ---
@bot.message_handler(func=lambda msg: True)
def handle_messages(message):
    if not check_user_access(message):
        return

    txt = message.text

    if txt in ["🎯 Interfaol metod", "/metod"]:
        bot.reply_to(message, "🎨 Dars mavzusi uchun interfaol metod tayyorlanmoqda...")
        try:
            matn = generate_ai_post(mavzu_turi="metod")
            safe_send_to_channel(matn)
            bot.reply_to(message, "✅ Interfaol metod kanalga chiqarildi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

    elif txt in ["📜 G'azal tahlili", "/gazal"]:
        bot.reply_to(message, "⏳ G'azal va bayt tahlili tayyorlanmoqda...")
        try:
            matn = generate_ai_post(mavzu_turi="gazal")
            safe_send_to_channel(matn)
            bot.reply_to(message, "✅ G'azal tahlili kanalga chiqdi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

    elif txt in ["📖 So'z izohi (O'TIL)", "/izoh"]:
        bot.reply_to(message, "⏳ O'TIL asosida so'z izohi tayyorlanmoqda...")
        try:
            matn = generate_ai_post(mavzu_turi="izoh")
            safe_send_to_channel(matn)
            bot.reply_to(message, "✅ So'z izohi kanalga chiqdi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

    elif txt in ["🔍 Etimologiya", "/etimologiya"]:
        bot.reply_to(message, "⏳ So'z etimologiyasi tayyorlanmoqda...")
        try:
            matn = generate_ai_post(mavzu_turi="etimologiya")
            safe_send_to_channel(matn)
            bot.reply_to(message, "✅ Etimologiya kanalga chiqdi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

    elif txt in ["📝 Grammatika", "/post"]:
        bot.reply_to(message, "⏳ Qiyin grammatik qoida tahlili tayyorlanmoqda...")
        try:
            matn = generate_ai_post(mavzu_turi="ilmiy")
            safe_send_to_channel(matn)
            bot.reply_to(message, "✅ Grammatik post kanalga chiqdi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

    elif txt in ["📚 Adabiyot tahlili", "/adabiyot"]:
        bot.reply_to(message, "⏳ Badiiy asar tahlili tayyorlanmoqda...")
        try:
            matn = generate_ai_post(mavzu_turi="adabiyot")
            safe_send_to_channel(matn)
            bot.reply_to(message, "✅ Adabiy post kanalga chiqdi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

    elif txt in ["✍️ Namunaviy esse", "/esse"]:
        bot.reply_to(message, "⏳ Esse namunasi tayyorlanmoqda...")
        try:
            matn = generate_ai_post(mavzu_turi="esse")
            safe_send_to_channel(matn)
            bot.reply_to(message, "✅ Esse tavsiyasi kanalga chiqdi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

    elif txt in ["🧠 BMB Quiz Test", "/test"]:
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
            bot.reply_to(message, "✅ Quiz test kanalga muvaffaqiyatli chiqarildi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

    elif txt in ["🎲 Tasodifiy gavhar", "/random"]:
        tanlov = random.choice(["metod", "gazal", "izoh", "etimologiya", "ilmiy", "adabiyot", "esse", "fakt", "motivatsiya"])
        bot.reply_to(message, "🎲 Tasodifiy material tayyorlanmoqda...")
        try:
            matn = generate_ai_post(mavzu_turi=tanlov)
            safe_send_to_channel(matn)
            bot.reply_to(message, "✅ Kanalga muvaffaqiyatli chiqdi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")
    else:
        bot.reply_to(message, "Quyidagi tugmalardan birini tanlang:", reply_markup=get_main_menu())

print("AI Tilshunos boti muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()

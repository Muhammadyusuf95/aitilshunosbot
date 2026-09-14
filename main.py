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
    return "AI Tilshunos & Metodist v3.0 Faol!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- SOZLAMALAR ---
TELEGRAM_TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@onatilidanyordam"

# DIQQAT: Bu yerga @userinfobot orqali olgan o'z Telegram ID raqamingizni yozing:
ADMIN_ID = 123456789  # O'z ID raqamingiz bilan almashtiring

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

IMZO = (
    "\n\n────────────────\n"
    f"🌟 **Rasmiy kanal:** {CHANNEL_USERNAME}\n"
    "✨ **Pedagogik & Ilmiy bot:** @aitilshunosbot"
)

# --- MENYULAR DIZAYNI ---
def get_main_menu():
    markup = tele_types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        tele_types.KeyboardButton("🎯 Interfaol metodlar"),
        tele_types.KeyboardButton("📜 G'azal va bayt tahlili")
    )
    markup.add(
        tele_types.KeyboardButton("📖 So'z izohi (O'TIL)"),
        tele_types.KeyboardButton("🔍 So'z etimologiyasi")
    )
    markup.add(
        tele_types.KeyboardButton("📝 Grammatika & Qoidalar"),
        tele_types.KeyboardButton("📚 Adabiy tahlil")
    )
    markup.add(
        tele_types.KeyboardButton("✍️ Namunaviy esse"),
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
        "grammatika": ("✍️ Qoidani o'zim kiritaman", "🎲 Tasodifiy qoida"),
        "adabiyot": ("✍️ Asarni o'zim kiritaman", "🎲 Tasodifiy asar tahlili"),
        "esse": ("✍️ Esse mavzusini kiritaman", "🎲 Tasodifiy esse rejasi")
    }
    btn1, btn2 = labels.get(category, ("✍️ O'zim kiritaman", "🎲 Tasodifiy"))
    markup.add(tele_types.KeyboardButton(btn1), tele_types.KeyboardButton(btn2))
    markup.add(tele_types.KeyboardButton("🔙 Asosiy menyu"))
    return markup

# --- XABAR YUBORISH STRATEGIYASI (KANAL YOKI BOT FOYDALANUVCHISI) ---
def deliver_response(user_id, text):
    if len(text) > 3900:
        text = text[:3900] + "...\n*(Qisqartirildi)*"

    if user_id == ADMIN_ID:
        try:
            bot.send_message(CHANNEL_USERNAME, text, parse_mode="Markdown")
            bot.send_message(user_id, "✅ Natija **@onatilidanyordam** kanaliga e'lon qilindi!", parse_mode="Markdown")
        except Exception:
            bot.send_message(CHANNEL_USERNAME, text)
            bot.send_message(user_id, "✅ Natija kanalga chiqarildi (oddiy formatda).")
    else:
        try:
            bot.send_message(user_id, text, parse_mode="Markdown")
        except Exception:
            bot.send_message(user_id, text)

# --- MAJBURIY OBUNA ---
def is_subscribed(user_id):
    if user_id == ADMIN_ID:
        return True
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

# --- GEMINI ILMIY TIZIMI ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston umumta'lim maktablari Ona tili va adabiyoti darsliklari, "
    "5 jildli 'O'zbek tilining izohli lug'ati' (O'TIL) hamda Shavkat Rahmatullayevning "
    "'O'zbek tilining etimologik lug'ati' mezonlari asosida tahlil beruvchi nufuzli metodist va leksikografsiz.\n"
    "1. Metodlar ishlab chiqilganda: Mavzu, metod nomi, darsdagi o'rni, qadamma-qadam qo'llash tartibi va "
    "darslikdan namunaviy topshiriq to'liq keltirilsin.\n"
    "2. So'z izohida: O'TIL mezonida barcha leksik ma'nolari va matndan misol berilsin.\n"
    "3. Etimologiyada: So'zning birlamchi tarixiy ildizi (turkiy, arabiy, forsiy), fonetik o'zgarishlari tushuntirilsin.\n"
    "4. Oxirida '📚 Manba:' ko'rsatilsin.\n"
    "5. Siyosiy, diniy, davlatga zid yoki shaxs sha'niga tegadigan mavzular qat'iyan man etiladi."
)

def generate_ai_content(prompt_text):
    full_prompt = (
        f"{prompt_text}\n\n"
        "Talablar: Telegram Markdown formatida, emojilar va aniq bo'limlar bilan, 2200 belgidan oshmasin. "
        "Oxirida '📚 Manba:' keltirilsin."
    )
    response = ai_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.4
        )
    )
    return response.text.strip() + IMZO

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
    response = ai_client.models.generate_content(
        model="gemini-3.6-flash",
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

# --- START VA OBUNA BOShQARUVI ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return
    text = (
        "╔════════════════════════╗\n"
        "  ✨ **AI TILSHUNOS METODIST PLATFORMASI**\n"
        "╚════════════════════════╝\n\n"
        "Assalomu alaykum! Maktab darsliklari, O'TIL va etimologik manbalar asosida xizmat ko'rsatuvchi intellektual tizimga xush kelibsiz.\n\n"
        "👇 **Quyidagi bo'limlardan birini tanlang:**"
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

# --- MATN SO'RASH QADAMLARI (CUSTOM INPUT HANDLERS) ---
def process_custom_step(message, prompt_template):
    user_input = message.text.strip()
    if user_input == "🔙 Asosiy menyu":
        send_welcome(message)
        return
    bot.reply_to(message, "⏳ Tahlil tayyorlanmoqda, kuting...")
    try:
        final_prompt = prompt_template.format(input=user_input)
        result = generate_ai_content(final_prompt)
        deliver_response(message.from_user.id, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")

# --- ASOSIY DISPETCHER ---
@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = message.text

    # 1. Asosiy menyuga qaytish
    if text == "🔙 Asosiy menyu":
        bot.send_message(message.chat.id, "Bosh menyudasiz:", reply_markup=get_main_menu())
        return

    # 2. Asosiy bo'limlar bosilganda sub-menyuni chiqarish
    if text == "🎯 Interfaol metodlar":
        bot.send_message(message.chat.id, "🎯 **Interfaol metodlar bo'limi:**\nYo'nalishni tanlang:", parse_mode="Markdown", reply_markup=get_sub_menu("metod"))
    elif text == "📜 G'azal va bayt tahlili":
        bot.send_message(message.chat.id, "📜 **Mumtoz g'azal va bayt tahlili:**\nYo'nalishni tanlang:", parse_mode="Markdown", reply_markup=get_sub_menu("gazal"))
    elif text == "📖 So'z izohi (O'TIL)":
        bot.send_message(message.chat.id, "📖 **O'zbek tilining izohli lug'ati (O'TIL):**\nYo'nalishni tanlang:", parse_mode="Markdown", reply_markup=get_sub_menu("izoh"))
    elif text == "🔍 So'z etimologiyasi":
        bot.send_message(message.chat.id, "🔍 **Etimologik tahlil bo'limi:**\nYo'nalishni tanlang:", parse_mode="Markdown", reply_markup=get_sub_menu("etimologiya"))
    elif text == "📝 Grammatika & Qoidalar":
        bot.send_message(message.chat.id, "📝 **Ona tili grammatikasi:**\nYo'nalishni tanlang:", parse_mode="Markdown", reply_markup=get_sub_menu("grammatika"))
    elif text == "📚 Adabiy tahlil":
        bot.send_message(message.chat.id, "📚 **Adabiy asarlar tahlili:**\nYo'nalishni tanlang:", parse_mode="Markdown", reply_markup=get_sub_menu("adabiyot"))
    elif text == "✍️ Namunaviy esse":
        bot.send_message(message.chat.id, "✍️ **BMB Esse rejalari:**\nYo'nalishni tanlang:", parse_mode="Markdown", reply_markup=get_sub_menu("esse"))

    # 3. BMB QUIZ TEST
    elif text == "🧠 BMB Quiz Test":
        bot.reply_to(message, "⏳ BMB mezonidagi Quiz testi tuzilmoqda...")
        try:
            quiz = generate_ai_quiz()
            target_chat = CHANNEL_USERNAME if message.from_user.id == ADMIN_ID else message.chat.id
            bot.send_poll(
                chat_id=target_chat,
                question=quiz["question"],
                options=quiz["options"],
                type="quiz",
                correct_option_id=quiz["correct_option_id"],
                explanation=quiz.get("explanation", ""),
                is_anonymous=True
            )
            if message.from_user.id == ADMIN_ID:
                bot.reply_to(message, "✅ Test kanalga joylandi!")
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik: {e}")

    # 4. SUB-MENYU: INTERFAOL METODLAR
    elif text == "✍️ Mavzuni o'zim kiritaman":
        msg = bot.reply_to(message, "✍️ Qaysi mavzu bo'yicha metod kerak? Mavzu nomini yozib yuboring:")
        p = "Ona tili yoki adabiyot fanidan aynan '{input}' mavzusi uchun zamonaviy interfaol metod ishlab chiqing. Format: Mavzu, Metod nomi, Darsdagi o'rni, Qo'llash tartibi (qadamma-qadam), Namunaviy darslik topshirig'i, Kutilayotgan natija."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "🎲 Tasodifiy metod":
        bot.reply_to(message, "⏳ Tasodifiy dars mavzusi bo'yicha metod tayyorlanmoqda...")
        p = "Ona tili yoki adabiyot darsliklaridan tasodifiy bitta mavzu tanlab, unga qiziqarli interfaol metod ishlab chiqing. Format: Mavzu, Metod nomi, Darsdagi o'rni, Qo'llash tartibi, Darslikdan topshiriq, Natija."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # 5. SUB-MENYU: SO'Z ETIMOLOGIYASI
    elif text == "✍️ So'zni o'zim kiritaman" and "etimologiya" in str(message):
        pass # pastdagi umumiy handler orqali ushlanadi

    # Matn orqali aniq ajratish:
    elif text == "🎲 Tasodifiy etimologiya":
        bot.reply_to(message, "⏳ Tasodifiy so'z etimologiyasi tayyorlanmoqda...")
        p = "Shavkat Rahmatullayevning 'O'zbek tilining etimologik lug'ati' asosida tasodifiy 1 ta so'zning tarixiy ildizi, o'zagi va semantik rivojlanishini tahlil qilib bering."
        deliver_response(message.from_user.id, generate_ai_content(p))

    elif text == "🎲 Tasodifiy so'z izohi":
        bot.reply_to(message, "⏳ O'TIL asosida tasodifiy so'z tahlil qilinmoqda...")
        p = "5 jildli 'O'zbek tilining izohli lug'ati' (O'TIL) asosida darsliklarda uchraydigan tasodifiy 1 ta ko'p ma'noli so'zning to'liq leksik tahlili va namunali gaplarini keltiring."
        deliver_response(message.from_user.id, generate_ai_content(p))

    elif text == "🎲 Tasodifiy g'azal":
        bot.reply_to(message, "⏳ Mumtoz g'azal tahlili tayyorlanmoqda...")
        p = "Mumtoz adabiyotimizdan (Navoiy, Bobur, Lutfiy yoki Ogahiy) 1-2 bayt keltirib, badiiy san'atlari, falsafiy ma'nosi va so'zlar sharhini bering."
        deliver_response(message.from_user.id, generate_ai_content(p))

    elif text == "🎲 Tasodifiy qoida":
        bot.reply_to(message, "⏳ Grammatik qoida tahlili tayyorlanmoqda...")
        p = "5-11-sinf Ona tili darsliklaridan qiyin yoki nozik 1 ta grammatik qoidaning chuqur tahlilini metodik tarzda tayyorlang."
        deliver_response(message.from_user.id, generate_ai_content(p))

    elif text == "🎲 Tasodifiy asar tahlili":
        bot.reply_to(message, "⏳ Adabiy asar tahlili tayyorlanmoqda...")
        p = "Adabiyot darsliklaridagi sara asarlardan biri, uning bosh g'oyasi, obrazlar tizimi va yozuvchi mahorati bo'yicha tahliliy post tayyorlang."
        deliver_response(message.from_user.id, generate_ai_content(p))

    elif text == "🎲 Tasodifiy esse rejasi":
        bot.reply_to(message, "⏳ Esse mavzusi va rejasi tayyorlanmoqda...")
        p = "BMB talablariga mos bitta namunaviy dolzarb esse mavzusi, uning puxta rejasi, asosiy tezislari va badiiy dalillarini bering."
        deliver_response(message.from_user.id, generate_ai_content(p))

    # Umumiy "O'zim kiritaman" tugmalari konteksti
    elif text == "✍️ So'zni o'zim kiritaman":
        msg = bot.reply_to(message, "✍️ Tahlil qilmoqchi bo'lgan so'zingizni yozib yuboring:")
        p = "Foydalanuvchi yuborgan '{input}' so'zini tahlil qiling: Agar so'rov etimologiya bo'lsa - Shavkat Rahmatullayev lug'ati bo'yicha tarixiy ildizi; agar izoh bo'lsa - O'TIL bo'yicha to'liq ma'nolarini bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "✍️ Baytni o'zim kiritaman":
        msg = bot.reply_to(message, "✍️ Tahlil qilmoqchi bo'lgan baytingizni yozib yuboring:")
        p = "Ushbu baytni badiiy tahlil qiling: '{input}'. San'atlari (tazod, tanosub, istiora va b.), ma'nosi va so'zlar sharhini bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "✍️ Qoidani o'zim kiritaman":
        msg = bot.reply_to(message, "✍️ Qaysi grammatik qoida yoki hodisani tahlil qilmoqchisiz? Yozib yuboring:")
        p = "Ona tili darsliklari mezonida '{input}' mavzusi/qoidasi bo'yicha ilmiy-metodik tushuntirish va misollar bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "✍️ Asarni o'zim kiritaman":
        msg = bot.reply_to(message, "✍️ Qaysi adabiy asar tahlili kerak? Asar nomini yozing:")
        p = "Adabiyot darsliklari asosida '{input}' asarini to'liq g'oyaviy, obrazlar va badiiy jihatdan tahlil qilib bering."
        bot.register_next_step_handler(msg, process_custom_step, p)

    elif text == "✍️ Esse mavzusini kiritaman":
        msg = bot.reply_to(message, "✍️ Esse mavzusini yozib yuboring:")
        p = "BMB talablari asosida '{input}' mavzusidagi esse uchun muqaddima, asosiy qism tezislari, xulosa va dalillar rejasini tuzing."
        bot.register_next_step_handler(msg, process_custom_step, p)

    else:
        bot.send_message(message.chat.id, "Iltimos, quyidagi menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu())

print("AI Tilshunos v3.0 to'liq ishga tushdi...")
bot.infinity_polling()

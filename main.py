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
    return "🎨 AI Tilshunos — Ijodiy va Ta'limiy Boti Faol!"

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

# --- ZAMONAVIY VA KREATIV MENYU (REPLY KEYBOARD) ---
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

# --- XAVFSIZ XABAR YUBORISH FUNKSIYASI ---
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
        f"Botning barcha innovatsion va ilmiy imkoniyatlaridan foydalanish uchun **{CHANNEL_USERNAME}** kanaliga a'zo bo'lishingiz lozim.\n\n"
        "Kanalga a'zo bo'lgach, quyidagi **«Obunani tekshirish»** tugmasini bosing:"
    )
    bot.send_message(chat_id, matn, parse_mode="Markdown", reply_markup=markup)

# --- GEMINI SISTEMA KO'RSATMASI ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi Xalq ta'limi tizimi va BMB talablari asosida faoliyat yurituvchi, "
    "ilg'or pedagogik texnologiyalar ustasi, tilshunos olim va ijodkor metodistsiz.\n\n"
    "ASOSIY VAZIFALAR:\n"
    "1. Muayyan ona tili yoki adabiyot mavzulari bo'yicha interfaol metodlar (FSMU, Klaster, Sinkveyn, "
    "Zinama-zina, Venn diagrammasi, Insert, Muammoli vaziyat) ishlab chiqish. Mavzuni aniq nomlash (sinf aytilishi shart emas), "
    "metodning nomi, darsdagi o'rni (kirish, yangi mavzu, mustahkamlash), qo'llash bosqichlari va tayyor darslik misollarini berish.\n"
    "2. O'zbek tilining izohli lug'ati (O'TIL) va Shavkat Rahmatullayevning etimologik lug'ati asosida akademik tahlillar berish.\n"
    "3. Mumtoz she'riyat (g'azal, qit'a, tuyuq) badiiy san'atlarini teran ochib berish.\n"
    "4. Har bir post oxirida albatta '📚 Manba:' ko'rsatilsin.\n\n"
    "QAT'IY CHEKLOVLAR: Siyosiy, diniy, huquqiy va davlatga zid har qanday mavzu qat'iyan man etiladi. "
    "Faqat sof, yuksak adabiy o'zbek tilida, estetik did va pedagogik etika bilan javob bering."
)

# --- GEMINI MATN TAYYORLASH FUNKSIYASI ---
def generate_ai_post(mavzu_turi="metod"):
    mavzular = {
        "metod": (
            "Ona tili yoki Adabiyot fanidan aniq bir mavzu (masalan: 'Ot turkumi', 'O'xshatish san'ati', "
            "'Sintaktik aloqalar', 'Alisher Navoiy ruboiylari' yoki 'Undalma va uning tinish belgilari') tanlang (sinf yozish shart emas). "
            "Ushbu mavzu uchun dars jarayonida o'quvchilarni faollashtiruvchi, zeriktirmaydigan 1 ta o'ziga xos INTERFAOL METOD ishlab chiqing.\n"
            "Format quyidagicha bo'lsin:\n"
            "📌 **Mavzu:** [Mavzu nomi]\n"
            "🎯 **Tavsiya etiladigan metod:** [Masalan: 'FSMU', 'Beshinchisi ortiqcha' yoki 'Mantiqiy zanjir']\n"
            "⏳ **Darsdagi o'rni:** [Yangi mavzuni tushuntirishda / Mustahkamlash bosqichida]\n"
            "🛠 **Metodning borishi va qoidalari:** [Qadamma-qadam aniq yo'riqnoma]\n"
            "💡 **Darslikdan namunaviy topshiriq:** [O'quvchilarga beriladigan amaliy matn/misol]\n"
            "✨ **Kutilayotgan pedagogik natija:** [Qisqa xulosa]"
        ),
        "gazal": (
            "Mumtoz adabiyotimizdan (Navoiy, Bobur, Lutfiy yoki Ogahiy) 1-2 bayt keltirib, "
            "uning badiiy san'atlari (tazod, tanosub, istiora va b.), falsafiy g'oyasi va so'zlar sharhini qamragan g'azal tahlilini yozing."
        ),
        "izoh": (
            "O'zbek tilining izohli lug'ati (O'TIL) asosida darsliklardagi 1-2 ta murakkab yoki qiziqarli so'zning "
            "to'liq leksik ma'nolari, uslubiy xoslanishi va namunali badiiy jumlalar bilan izohini bering."
        ),
        "etimologiya": (
            "O'zbek tilining etimologik lug'ati asosida 1-2 ta so'zning tarixiy o'zagi, fonetik o'zgarishi va ildizini ixcham tushuntiring."
        ),
        "ilmiy": "5-11-sinf Ona tili darsliklari asosida o'quvchilarga qiyinchilik tug'diradigan grammatik qoida bo'yicha metodik post yozing.",
        "adabiyot": "Adabiyot darsliklaridagi sara asarlar tahlili, qahramonlar ruhiyati va adib mahorati haqida post tayyorlang.",
        "esse": "BMB talablariga mos 1 ta namunaviy esse mavzusi, tuzilishi, reja bandlari va tayyor tezislari bilan yo'riqnoma bering.",
        "fakt": "Ona tili va adabiyot darsliklari bo'yicha qiziqarli ilmiy fakt yoki etnolingvistik ma'lumot keltiring.",
        "motivatsiya": "Ajdodlarimiz o'gitlaridan ilm-fan va kitob mutolaasiga chorlovchi ibratli post tayyorlang."
    }

    prompt = (
        f"{mavzular.get(mavzu_turi, mavzular['metod'])}\n\n"
        "TALABLAR:\n"
        "- Vizual ko'rinish kreativ, estetik jihatdan chiroyli va o'qishli bo'lsin.\n"
        "- Uzunligi 2200 belgidan oshmasin.\n"
        "- Oxirida '📚 Manba:' aniq yozilsin.\n"
        "- Ortiqcha gap-so'zlarsiz, to'g'ridan-to'g'ri kanalga chiqarishga tayyor holatda bering."
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
        "Ona tili yoki Adabiyot fanidan BMB (DTM) standartida 4 variantli (A, B, C, D) 1 ta mantiqiy Quiz test tuzing. "
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
        raw_text = raw_text.split("

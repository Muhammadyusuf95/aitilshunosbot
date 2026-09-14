import telebot

TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
bot = telebot.TeleBot(TOKEN)

# Mana shu yerga o'z kanalingiz nomini yozasiz:
CHANNEL_USERNAME = "@Onatilidanyordam"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Assalomu alaykum! AI Tilshunos botiga xush kelibsiz.\n\n"
        "Kanalga post chiqarish uchun /post buyrug'ini yuboring."
    )

@bot.message_handler(commands=['post'])
def publish_to_channel(message):
    post_matni = (
        "📚 **Ilmiy-ma'rifiy xazina**\n\n"
        "Ona tilimizning boy madaniy merosi, tarixiy leksikasi va etnomadaniy "
        "qadriyatlari bebaho boylikdir.\n\n"
        "💡 *Kanalimizda tilshunoslik tahlillari va qiziqarli manbalar berib boriladi.*"
    )
    try:
        bot.send_message(CHANNEL_USERNAME, post_matni, parse_mode="Markdown")
        bot.reply_to(message, "✅ Post muvaffaqiyatli kanalga chiqdi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}\n(Bot kanalda admin ekanligini tekshiring)")

print("Bot muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()
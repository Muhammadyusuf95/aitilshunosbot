"""Inline rejim: testni ulashish kartochkasi (chuqur havola orqali botga olib keladi)."""
from telebot import types as tt

from app import config
from app.runtime import bot


@bot.inline_handler(func=lambda q: True)
def inline_share(query):
    from app.handlers.tests import PENDING
    qid = (query.query or "").strip()
    item = PENDING.get(qid)
    link = f"https://t.me/{config.BOT_USERNAME}?start={qid}" if item else f"https://t.me/{config.BOT_USERNAME}"
    title = f"🧠 {item['title']}" if item else "AI Tilshunos"
    desc = (f"{len(item['questions'])} ta savol — bosing va ulashing" if item
            else "Ona tili va adabiyotga tayyorlanish uchun AI yordamchi")
    markup = tt.InlineKeyboardMarkup()
    markup.add(tt.InlineKeyboardButton("🚀 Testni boshlash" if item else "🤖 Botni ochish", url=link))
    text = (f"🧠 <b>{title[2:] if item else 'AI Tilshunos'}</b>\n\n{desc}\n\n"
            f"👇 Boshlash uchun tugmani bosing\n📢 {config.CHANNEL_USERNAME}")
    result = tt.InlineQueryResultArticle(
        id="1", title=title, description=desc,
        input_message_content=tt.InputTextMessageContent(text, parse_mode="HTML"),
        reply_markup=markup,
    )
    try:
        bot.answer_inline_query(query.id, [result], cache_time=5, is_personal=True)
    except Exception as e:  # noqa: BLE001
        print(f"[inline] {e}")

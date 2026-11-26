"""AI Tilshunos — kirish nuqtasi."""
import sys
import threading
import time

from app import config


def main():
    if not config.TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN o'rnatilmagan. Hosting sozlamalarida (yoki .env faylda) TELEGRAM_TOKEN ni kiriting.")
        sys.exit(1)

    from app.db import get_db
    from app.handlers import register_all
    from app.runtime import bot
    from app import scheduler, web
    from telebot import types

    db = get_db()
    print(f"[start] AI Tilshunos {config.BOT_VERSION} | baza: {'PostgreSQL' if db.is_pg else 'SQLite'} | "
          f"AI: {'ulangan' if config.GEMINI_API_KEY else 'KALIT YO‘Q'}")
    register_all()

    threading.Thread(target=web.run_web, daemon=True).start()
    threading.Thread(target=scheduler.auto_poster, daemon=True).start()
    threading.Thread(target=scheduler.keep_alive, daemon=True).start()

    try:
        bot.set_my_commands([
            types.BotCommand("start", "Bosh sahifa"), types.BotCommand("daily", "Kun savoli"),
            types.BotCommand("profile", "Shaxsiy kabinet"), types.BotCommand("top", "Reyting"),
            types.BotCommand("menu", "Asosiy menyu"), types.BotCommand("jadval", "Kanal testlari jadvali"),
            types.BotCommand("testxabar", "Kanal testi xabarnomasi (yoqish/o'chirish)"), types.BotCommand("cancel", "Amalni bekor qilish"),
            types.BotCommand("help", "Yordam"),
        ])
        bot.remove_webhook()
    except Exception as e:  # noqa: BLE001
        print(f"[start] buyruqlarni o'rnatib bo'lmadi: {e}")

    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30,
                                 allowed_updates=["message", "callback_query", "poll", "poll_answer", "inline_query"])
        except Exception as e:  # noqa: BLE001
            print(f"[polling] xato: {e}; 5 soniyadan so'ng qayta ulanadi")
            time.sleep(5)


if __name__ == "__main__":
    main()

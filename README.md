# AI Tilshunos v12

Ona tili va adabiyot bo'yicha Telegram bot: abituriyent, o'qituvchi, talaba va tadqiqotchilar uchun.

## Ishga tushirish
1. `pip install -r requirements.txt`
2. `.env.example` ni `.env` ga nusxalab to'ldiring (yoki hosting "Environment" bo'limiga kiriting). **Majburiy:** `TELEGRAM_TOKEN`, `GEMINI_API_KEY`.
3. `python main.py`

`DATABASE_URL` (Neon/Postgres) bo'lmasa, bot avtomatik SQLite bilan ishlaydi. Eski `users` jadvali saqlanadi, yangi ustunlar o'zi qo'shiladi.
Bot kanalda (`CHANNEL_USERNAME`) **admin** bo'lishi kerak (obunani tekshirish va avto-post uchun).

## Tuzilma
```
main.py            kirish nuqtasi
app/config.py      sozlamalar (faqat muhit o'zgaruvchilari)
app/db.py          Postgres/SQLite qatlami
app/ai.py          Gemini (zaxira modellar, JSON, rasm)
app/questions.py   savollar: baza.json + AI aralash
app/practice.py    yakka mashq mantiqi
app/textfmt.py     Markdown→HTML, uzun matnni bo'lish
app/handlers/      core, tools, essays, tests, group, profile, admin, inline
app/web.py         Mini-App reyting + /health
app/scheduler.py   kunlik avto-post
data/              baza.json, namunaviy esselar
tests/             pytest (soxta Telegram bilan)
```
Testlar: `python -m pytest tests -q`

## Kanal jadvali (Toshkent vaqti, `BOT_TZ` bilan o'zgaradi)
07:30 Kun savoli · 19:30 Tezkor 10 talik · 20:00 Mavzulashtirilgan 30 talik · 20:30 BMB 30 talik · 21:00 Attestatsiya 40 talik.
Bot kanalda **admin** bo'lib, post va so'rovnoma yuborish huquqiga ega bo'lishi shart. Kanal so'rovnomalari anonim (Telegram cheklovi).

## Mavzu himoyasi
Kirish filtri (`app/security.py`) + AI tizim ko'rsatmasi (`OFFTOPIC_REFUSED`) + chiqish filtri + ogohlantirishlar (24 soatda 3 marta → 24 soat cheklov; admin: `/unblock ID`).

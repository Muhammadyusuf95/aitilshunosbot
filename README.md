# AI Tilshunos v12.3

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


## v12.1 — o'sish funksiyalari
- 🔗 Kanal → bot: kanal postlari/yakuniy xabarlarda botga o'tish tugmalari (`?start=daily|quick`)
- 🔔 Eslatmalar: kuniga 18:00 da (seriya uzilishi arafasida / 3 kun kirmaganlarga), `/eslatma` bilan o'chirish
- 🏆 Haftalik g'oliblar: yakshanba 19:00, TOP-3 kanalga + XP + nishon. Sovrin matni: `WEEKLY_PRIZE` env
- 📅 Imtihon sanog'i va kunlik reja (➕ Yana → Imtihon sanasi)
- 🖼 Natija kartochkasi (PNG, Pillow) — test yakunida
- ⚔️ Do'st bilan bellashuv (`?start=duel_ID`)
- 🏫 Sinf rejimi: o'qituvchi sinf kodi, topshiriq, natijalar; o'quvchi `?start=cls_KOD`
Soddalashtirish: Aqliy mashq olib tashlandi, Qadimgi turkiy → etimologiyaga qo'shildi, Tadqiqotchi → Til asboblari ichida, asosiy menyu qisqartirildi.


## v12.2 — quiz testlarining yangi tartibi
- ✋ **Lobby:** har bir guruh/kanal testi kamida **2 kishi** «Men tayyorman»ni bosgach boshlanadi (`MIN_PLAYERS`). Bir kishi ikki marta bossa hisoblanmaydi; «Hozir boshlash» olib tashlandi.
- ⏸ **Pauza:** ketma-ket 2 ta savolga hech kim javob bermasa, test to'xtaydi va kamida bir kishi «▶️ Davom etish»ni bosgach davom etadi. `QUIZ_PAUSE_MAX_MIN` (standart 60) daqiqa ichida bosilmasa, test yakunlanadi.
- 🕒 **Jadval:** kanaldagi asosiy vaqtlar saqlanadi. Faqat pauza davomiyligi shu kungi keyingi testlarga qo'shiladi (kv: `sched_shift:SANA`). Lobby keyingi test vaqtiga ulguradigan qilib yopiladi, shuning uchun ishtirokchi kutish jadvalni surmaydi; oxirgi test lobbisi `LAST_LOBBY_MIN` daqiqa ochiq.
- 📝 **Ochiq savollar:** so'rovnomalar endi yopilmaydi (`open_period` yo'q). Test tugagach kirgan odam avval o'z variantini belgilaydi, shundan so'ng to'g'ri javob va izohni ko'radi; javob belgilamaganga savol ishlanmagandek ko'rinadi. Reytingga faqat savol vaqti ichidagi javoblar kiradi.
- 📅 `/jadval` — bugungi kanal jadvali (surilgan vaqtlar bilan); 🔔 `/testxabar` — lobby ochilganda xabar olish (faqat foydalanuvchi o'zi yoqsa; 20 daqiqada ko'pi bilan 1 ta xabar).
- 📣 Lobbida «Do'stni chaqirish» tugmasi, yakuniy xabarda «Test boshiga o'tish» havolasi.
- Kanal so'rovnomalaridagi ovozlarni bilish uchun bot `poll` yangilanishlarini ham qabul qiladi (`allowed_updates`).

## v12.3 — kanal testi reytingi botda
- 🏆 Kanal testi yakunlangach, kanal postidagi «Test reytingi (botda)» tugmasi botdagi shu testning reytingini ochadi.
- Kanal so'rovnomalari anonim bo'lgani uchun, kanal ovozlari reytingga kirmaydi. Test savollari saqlanadi (`channel_tests`) va foydalanuvchi uni botda «📝 Testni botda ishlash» orqali ishlaydi.
- Har bir test o'z reytingiga ega (`channel_results`): to'g'ri javoblar soni, teng bo'lsa — tezlik. Har kishi uchun faqat birinchi urinish hisobga olinadi. Ishtirokchilar ko'paygani sari o'rinlar o'zgaradi («🔄 Yangilash»).
- Botda ishlangan natija umumiy reytingga ham qo'shiladi (XP va haftalik TOP).
- `/testlar` — so'nggi kanal testlari ro'yxati va ularning reytingi.
- Havola: `?start=ct_ID`.

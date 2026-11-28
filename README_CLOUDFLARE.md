# AI Tilshunos Bot — Cloudflare Workers + D1 + Durable Objects

Ushbu loyiha `aitilshunosbot` Telegram botining **Cloudflare Workers** infratuzilmasiga to'liq ko'chirilgan (serverless, bepul tarifda 24/7 uxlamasdan ishlaydigan) versiyasi.

## Arxitektura
- **Cloudflare Workers (`src/index.js`)**: Telegram Webhook va 7 ta Cron Trigger (kun savoli, seriya eslatmalari, haftalik g'oliblar, kechki viktorinalar).
- **Cloudflare D1 (`schema.sql`)**: SQLite bazasi (foydalanuvchilar, test natijalari, xatolar banki, yutuqlar, sinflar, kanal testlari, holatlar).
- **Cloudflare Durable Objects (`src/quiz_room.js`)**: Guruh viktorinalari (`/quiz`) uchun real-vaqt xotirasi va taymerlari (`alarm()`).
- **Bundled Data (`src/data/baza.json`, `src/data/essays.json`)**: Savollar bazasi va namuna esselar Worker ichiga integratsiya qilingan.

## Ishga tushirish bosqichlari (5 daqiqa)

### 1. Bog'liqliklarni o'rnatish
```bash
npm install
npx wrangler login
```

### 2. D1 ma'lumotlar bazasini yaratish
```bash
npx wrangler d1 create aitilshunos-db
```
Chiqgan `database_id` qiymatini `wrangler.toml` faylidagi `REPLACE_WITH_YOUR_D1_DATABASE_ID` o'rniga yozing.

So'ng jadvallarni yarating:
```bash
npm run db:init
```

### 3. Maxfiy kalitlarni (Secrets) kiritish
```bash
npx wrangler secret put TELEGRAM_TOKEN
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put WEBHOOK_SECRET
```
*(Eslatma: `WEBHOOK_SECRET` uchun istalgan maxfiy so'z kiriting, masalan `uztil2026secret`)*

### 4. Deploy qilish va Webhook ulash
```bash
npm run deploy
```
Deploy yakunlangach brauzerda quyidagi manzilni bir marta oching:
`https://aitilshunosbot.<sizning-subdomain>.workers.dev/set-webhook?secret=<WEBHOOK_SECRET>`

Tayyor! Bot 24/7 ishlaydi.

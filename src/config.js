export function getConfig(env) {
  const num = (val, def) => {
    const n = Number(val);
    return Number.isFinite(n) && val !== undefined && val !== "" ? n : def;
  };
  return {
    TELEGRAM_TOKEN: env.TELEGRAM_TOKEN || env.BOT_TOKEN || "",
    GEMINI_API_KEY: env.GEMINI_API_KEY || "",
    ADMIN_ID: String(env.ADMIN_ID || "5423849679"),
    CHANNEL_USERNAME: env.CHANNEL_USERNAME || "@onatilidanyordam",
    CHANNEL_URL: env.CHANNEL_URL || "https://t.me/onatilidanyordam",
    BOT_USERNAME: env.BOT_USERNAME || "aitilshunosbot",
    PUBLIC_URL: (env.PUBLIC_URL || "").replace(/\/+$/, ""),
    GEMINI_MODELS: (env.GEMINI_MODELS || "gemini-2.5-flash,gemini-2.5-flash-lite")
      .split(",")
      .map(s => s.trim())
      .filter(Boolean),
    AI_COOLDOWN_SEC: num(env.AI_COOLDOWN_SEC, 4),
    AI_DAILY_LIMIT: num(env.AI_DAILY_LIMIT, 60),
    MIN_PLAYERS: num(env.MIN_PLAYERS, 2),
    LOBBY_TTL_SEC: num(env.LOBBY_TTL_SEC, 900),
    QUIZ_PAUSE_MAX_MIN: num(env.QUIZ_PAUSE_MAX_MIN, 60),
    LAST_LOBBY_MIN: num(env.LAST_LOBBY_MIN, 60),
    BOT_TZ: env.BOT_TZ || "Asia/Tashkent",
    BOT_VERSION: env.BOT_VERSION || "v12.3-cf",
    WEEKLY_PRIZE: env.WEEKLY_PRIZE || "",
  };
}

export function tashkentDate(offsetDays = 0) {
  const now = new Date(Date.now() + 5 * 3600 * 1000 + offsetDays * 86400 * 1000);
  return now.toISOString().slice(0, 10);
}

export function tashkentNow() {
  return new Date(Date.now() + 5 * 3600 * 1000);
}

export function utcNowStr() {
  return new Date().toISOString().replace("T", " ").slice(0, 19);
}

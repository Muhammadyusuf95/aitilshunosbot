import { tashkentDate } from "./config.js";
import { esc } from "./textfmt.js";
import { checkSecurityViolation, checkHardViolation, SECURITY_WARNING, BLOCKED_TEXT, STRIKE_LIMIT, STRIKE_WINDOW } from "./security.js";
import { subscribeKb } from "./keyboards.js";

export class BotContext {
  constructor(env, cfg, db, tg) {
    this.env = env;
    this.cfg = cfg;
    this.db = db;
    this.tg = tg;
  }

  isAdmin(uid) {
    return String(uid) === String(this.cfg.ADMIN_ID);
  }

  displayName(user) {
    const first = (user?.first_name || "").trim();
    const last = (user?.last_name || "").trim();
    const full = `${first} ${last}`.trim();
    if (full) return full;
    if (user?.username) return `@${user.username}`;
    return `Foydalanuvchi ${user?.id || ""}`;
  }

  async checkAiGuard(uid, chatId, text = "") {
    if (this.isAdmin(uid)) return true;

    const now = Math.floor(Date.now() / 1000);
    const blockedUntil = Number((await this.db.kvGet(`block:${uid}`, 0)) || 0);
    if (now < blockedUntil) {
      await this.tg.sendHtml(chatId, BLOCKED_TEXT);
      return false;
    }

    if (text && checkSecurityViolation(text)) {
      const hard = checkHardViolation(text);
      const key = `strikes:${uid}`;
      let raw = [];
      try { raw = JSON.parse((await this.db.kvGet(key, "[]")) || "[]"); } catch {}
      raw = raw.filter(t => now - Number(t) < STRIKE_WINDOW);
      raw.push(now);
      if (hard) raw.push(now);
      await this.db.kvSet(key, JSON.stringify(raw));

      if (raw.length >= STRIKE_LIMIT) {
        await this.db.kvSet(`block:${uid}`, now + STRIKE_WINDOW);
        await this.db.kvSet(key, "[]");
        await this.tg.sendHtml(chatId, BLOCKED_TEXT);
      } else {
        await this.tg.sendHtml(
          chatId,
          `${SECURITY_WARNING}\n\n<i>Ogohlantirish: ${raw.length}/${STRIKE_LIMIT}.</i>`
        );
      }
      return false;
    }

    const lastAi = Number((await this.db.kvGet(`last_ai:${uid}`, 0)) || 0);
    const wait = this.cfg.AI_COOLDOWN_SEC - (now - lastAi);
    if (wait > 0) {
      await this.tg.sendHtml(chatId, `⏳ Biroz kuting — yana <b>${Math.ceil(wait)} soniyadan</b> so'ng urinib ko'ring.`);
      return false;
    }

    const today = tashkentDate();
    const dKey = `ai_daily:${uid}:${today}`;
    const used = Number((await this.db.kvGet(dKey, 0)) || 0);
    if (used >= this.cfg.AI_DAILY_LIMIT) {
      await this.tg.sendHtml(
        chatId,
        `📊 Bugungi AI so'rovlar limiti (<b>${this.cfg.AI_DAILY_LIMIT} ta</b>) tugadi. ` +
        "Bazadagi testlar, kun savoli va alifbo o'girish cheklovsiz ishlaydi!"
      );
      return false;
    }

    await this.db.kvSet(`last_ai:${uid}`, now);
    await this.db.kvSet(dKey, used + 1);
    return true;
  }

  async ensureSub(uid, chatId, user = null, cbId = null) {
    if (this.isAdmin(uid) || !this.cfg.CHANNEL_USERNAME) return true;
    const okKey = `sub_ok:${uid}`;
    const cached = Number((await this.db.kvGet(okKey, 0)) || 0);
    if (Math.floor(Date.now() / 1000) - cached < 300) return true;

    try {
      const m = await this.tg.getChatMember(this.cfg.CHANNEL_USERNAME, uid);
      if (["member", "administrator", "creator"].includes(m.status)) {
        await this.db.kvSet(okKey, Math.floor(Date.now() / 1000));
        return true;
      }
    } catch {
      return true;
    }

    const name = user ? esc(user.first_name || "Do'st") : "Do'st";
    const text =
      `👋 Assalomu alaykum, <b>${name}</b>!\n\n` +
      `Botdan to'liq foydalanish uchun rasmiy kanalimizga a'zo bo'ling:\n` +
      `📢 <b>${esc(this.cfg.CHANNEL_USERNAME)}</b>\n\n` +
      `A'zo bo'lgach, <b>«✅ Tekshirish»</b> tugmasini bosing.`;
    if (cbId) await this.tg.answerCallback(cbId, "Avval kanalga a'zo bo'ling!", true);
    await this.tg.sendHtml(chatId, text, subscribeKb(this.cfg.CHANNEL_URL));
    return false;
  }

  async touchAndNotify(user, chatId) {
    const info = await this.db.touchUser(user);
    if (info.new_day && !info.is_new_user) {
      const notes = [];
      if (info.broken) {
        notes.push(`💔 Oldingi <b>${info.prev_streak} kunlik</b> seriyangiz uzildi, yangisi boshlandi.`);
      }
      notes.push(`🔥 <b>${info.streak}-kun ketma-ket!</b> +${info.gained} XP`);
      await this.tg.sendHtml(chatId, notes.join("\n"));
    }
    if (info.streak >= 3 && await this.db.awardBadge(user.id, "streak_3")) {
      await this.tg.sendHtml(chatId, "🏅 Yangi yutuq: <b>🔥 Uch kunlik seriya</b>!");
    }
    if (info.streak >= 7 && await this.db.awardBadge(user.id, "streak_7")) {
      await this.tg.sendHtml(chatId, "🏅 Yangi yutuq: <b>⚡ Haftalik seriya</b>!");
    }
    if (info.streak >= 30 && await this.db.awardBadge(user.id, "streak_30")) {
      await this.tg.sendHtml(chatId, "🏅 Yangi yutuq: <b>🌟 Oylik seriya</b>!");
    }
    return info;
  }
}

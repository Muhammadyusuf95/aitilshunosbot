import { tashkentDate, tashkentNow } from "./config.js";
import { dailyQuestion } from "./bank.js";
import { esc, card } from "./textfmt.js";
import { btn } from "./keyboards.js";

const LETTER = ["A", "B", "C", "D"];

export async function runScheduled(ctx, cronExpr) {
  const now = tashkentNow();
  const hhmm = `${String(now.getUTCHours()).padStart(2, "0")}:${String(now.getUTCMinutes()).padStart(2, "0")}`;
  const dow = now.getUTCDay();

  if (cronExpr === "30 2 * * *" || hhmm === "07:30") {
    const today = tashkentDate();
    if (await ctx.db.kvGet("cron:daily_ch") !== today) {
      await ctx.db.kvSet("cron:daily_ch", today);
      const q = dailyQuestion(today);
      if (q && ctx.cfg.CHANNEL_USERNAME) {
        const opts = q.options.map((o, i) => `<b>${LETTER[i]})</b> ${esc(o)}`).join("\n");
        const text = card(
          "📅 Kun savoli · " + today,
          esc(q.bolim || "Ona tili va adabiyot"),
          `${esc(q.question)}\n\n${opts}\n\n` +
          `<i>Javobingizni tekshirish va XP olish uchun botga o'ting 👇</i>`
        );
        try {
          await ctx.tg.sendHtml(
            ctx.cfg.CHANNEL_USERNAME,
            text,
            { inline_keyboard: [[{ text: "🎯 Javob berish (+20 XP)", url: `https://t.me/${ctx.cfg.BOT_USERNAME}?start=daily` }]] }
          );
        } catch {}
      }
    }
  }

  if (cronExpr === "0 13 * * *" || hhmm === "18:00") {
    const today = tashkentDate();
    if (await ctx.db.kvGet("cron:remind") !== today) {
      await ctx.db.kvSet("cron:remind", today);
      const yest = tashkentDate(-1);
      const twoAgo = tashkentDate(-2);
      const users = await ctx.db.usersForReminder([yest, twoAgo]);
      for (const u of users) {
        try {
          const st = Number(u.streak || 0);
          const msg = st >= 2
            ? `🔥 Salom, <b>${esc(u.first_name || "Do'st")}</b>! <b>${st} kunlik</b> seriyangiz uzilib qolmasligi uchun bugun kamida 1 ta savolga javob bering!`
            : `👋 Salom, <b>${esc(u.first_name || "Do'st")}</b>! Bugungi <b>Kun savoli</b> sizni kutmoqda (+20 XP).`;
          await ctx.tg.sendHtml(u.user_id, msg, { inline_keyboard: [[btn("📅 Kun savoli", "daily_start")]] });
        } catch (e) {
          if (e.code === 403) await ctx.db.setStatus(u.user_id, "blocked");
        }
      }
    }
  }

  if (cronExpr === "0 14 * * 0" || (dow === 0 && hhmm === "19:00")) {
    const wk = `wk_${tashkentDate()}`;
    if (await ctx.db.kvGet("cron:weekly") !== wk) {
      await ctx.db.kvSet("cron:weekly", wk);
      const top = await ctx.db.leaderboard("week", 3);
      if (top.length) {
        const medals = ["🥇", "🥈", "🥉"];
        const lines = [];
        for (let i = 0; i < top.length; i++) {
          const r = top[i];
          await ctx.db.awardBadge(r.user_id, "weekly_winner");
          await ctx.db.addPoints(r.user_id, [100, 60, 40][i] || 30);
          lines.push(`${medals[i]} <b>${esc(r.name)}</b> — ${r.correct}/${r.total}`);
        }
        const prize = ctx.cfg.WEEKLY_PRIZE ? `\n\n🎁 Sovg'a: <b>${esc(ctx.cfg.WEEKLY_PRIZE)}</b>` : "";
        if (ctx.cfg.CHANNEL_USERNAME) {
          try {
            await ctx.tg.sendHtml(
              ctx.cfg.CHANNEL_USERNAME,
              card("🏆 Hafta g'oliblari e'lon qilindi!", "@aitilshunosbot", lines.join("\n") + prize)
            );
          } catch {}
        }
      }
    }
  }

  if (["30 14 * * *", "0 15 * * *", "30 15 * * *", "0 16 * * *"].includes(cronExpr)) {
    const slot = `${tashkentDate()}_${hhmm}`;
    if (await ctx.db.kvGet("cron:qalert") !== slot) {
      await ctx.db.kvSet("cron:qalert", slot);
      const users = await ctx.db.usersForQuizAlert();
      for (const u of users) {
        try {
          await ctx.tg.sendHtml(
            u.user_id,
            `⏰ <b>Kechki mashq vaqti (${hhmm})!</b>\nBilimingizni mustahkamlash uchun 10 savollik tezkor testni boshlang:`,
            { inline_keyboard: [[btn("🎲 Tezkor test (10 savol)", "q_quick")]] }
          );
        } catch (e) {
          if (e.code === 403) await ctx.db.setStatus(u.user_id, "blocked");
        }
      }
    }
  }
}

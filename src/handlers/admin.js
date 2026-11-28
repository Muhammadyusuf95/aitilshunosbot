import { esc, card } from "../textfmt.js";
import { totalCount } from "../bank.js";
import { generateQuiz } from "../ai.js";
import { adminMenu, adminUsersNav, confirmKb, btn } from "../keyboards.js";

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

export async function openAdminMenu(ctx, chatId, editMid = null) {
  const c = await ctx.db.userCounts();
  const s = await ctx.db.summaryCounts();
  const txt = card(
    "🛡 Admin boshqaruv paneli",
    `Cloudflare Workers · ${ctx.cfg.BOT_VERSION}`,
    `👥 Jami foydalanuvchilar: <b>${c.total}</b> (faol: ${c.active}, blok: ${c.blocked})\n` +
    `📅 Bugun faol: <b>${c.today}</b> · Haftada: <b>${c.week}</b>\n` +
    `📝 Yechilgan testlar: <b>${s.tests}</b> (${s.participants} qatnashchi)\n` +
    `📚 Savollar bazasi: <b>${totalCount()} ta</b>`
  );
  if (editMid) await ctx.tg.editHtml(chatId, editMid, txt, adminMenu());
  else await ctx.tg.sendHtml(chatId, txt, adminMenu());
}

export async function handleAdminCallback(ctx, cq, data) {
  const uid = cq.from.id;
  if (!ctx.isAdmin(uid)) return false;
  const chatId = cq.message.chat.id;
  const mid = cq.message.message_id;
  const parts = data.split(":");
  const sub = parts[1];

  if (sub === "menu" || sub === "stats") {
    await openAdminMenu(ctx, chatId, mid);
    return true;
  }
  if (sub === "users") {
    const page = Number(parts[2] || 0);
    const c = await ctx.db.userCounts();
    const per = 8;
    const totalPages = Math.max(1, Math.ceil(c.total / per));
    const rows = await ctx.db.usersPage(page, per);
    const lines = rows.map(u => {
      const st = u.status === "blocked" ? "🚫" : "✅";
      const un = u.username ? `@${u.username}` : "";
      return `${st} <code>${u.user_id}</code> <b>${esc(u.first_name || "-")}</b> ${esc(un)} · ${u.points} XP`;
    });
    await ctx.tg.editHtml(
      chatId,
      mid,
      card(`👥 Foydalanuvchilar (${page + 1}/${totalPages})`, `Jami: ${c.total}`, lines.join("\n") || "Bo'sh"),
      adminUsersNav(page, totalPages)
    );
    return true;
  }
  if (sub === "broadcast") {
    await ctx.db.setState(uid, "adm_broadcast", {});
    await ctx.tg.sendHtml(chatId, "📢 <b>Barcha faol foydalanuvchilarga yuboriladigan xabarni yozing</b> (HTML mumkin):");
    return true;
  }
  if (sub === "broadcast_go") {
    const st = await ctx.db.getState(uid, 600);
    const text = st?.data?.text;
    await ctx.db.clearState(uid);
    if (!text) return true;
    const ids = await ctx.db.allUserIds(true);
    let ok = 0, fail = 0;
    await ctx.tg.editHtml(chatId, mid, `⏳ Yuborilmoqda (0/${ids.length})...`);
    for (const target of ids) {
      try {
        await ctx.tg.sendHtml(target, text);
        ok++;
      } catch (e) {
        fail++;
        if (e.code === 403) await ctx.db.setStatus(target, "blocked");
      }
      if ((ok + fail) % 25 === 0) await sleep(1000);
    }
    await ctx.tg.sendHtml(chatId, `✅ Xabar yuborish yakunlandi.\nYetkazildi: <b>${ok}</b> · Xato/blok: <b>${fail}</b>`);
    return true;
  }
  if (sub === "ch_post") {
    await ctx.db.setState(uid, "adm_ch_post", {});
    await ctx.tg.sendHtml(chatId, `📣 <b>${esc(ctx.cfg.CHANNEL_USERNAME)}</b> kanaliga joylanadigan post matnini yuboring:`);
    return true;
  }
  if (sub === "ch_test") {
    await ctx.db.setState(uid, "adm_ch_test", {});
    await ctx.tg.sendHtml(chatId, "📝 Kanal testi mavzusini yozing (10 ta savol AI bilan tuzilib kanalga tugma bilan joylanadi):");
    return true;
  }
  if (sub === "ch_board") {
    const rows = await ctx.db.leaderboard("week", 10);
    const medals = ["🥇", "🥈", "🥉"];
    const lines = rows.map((r, i) => `${i < 3 ? medals[i] : `${i + 1}.`} <b>${esc(r.name)}</b> — ${r.correct}/${r.total}`);
    const post = card(
      "🏆 Haftalik bilimdonlar reytingi",
      "@aitilshunosbot",
      (lines.join("\n") || "Hali natijalar yo'q") +
      `\n\n🎯 Siz ham bilimingizni sinang: @${ctx.cfg.BOT_USERNAME}`
    );
    await ctx.tg.sendHtml(ctx.cfg.CHANNEL_USERNAME, post);
    await ctx.tg.sendHtml(chatId, "✅ Haftalik reyting kanalga joylandi!");
    return true;
  }
  if (sub === "export") {
    const rows = await ctx.db.exportUsers();
    const header = "user_id,username,first_name,points,streak,best_streak,status,last_active,invites";
    const csv = [
      header,
      ...rows.map(r =>
        [r.user_id, r.username, r.first_name, r.points, r.streak, r.best_streak, r.status, r.last_active, r.invites]
          .map(v => `"${String(v ?? "").replace(/"/g, '""')}"`)
          .join(",")
      ),
    ].join("\n");
    await ctx.tg.sendDocumentBytes(chatId, new TextEncoder().encode("\uFEFF" + csv), "users_export.csv", `Jami: ${rows.length} ta`);
    return true;
  }
  if (sub === "health") {
    const t0 = Date.now();
    await ctx.db.one("SELECT 1 AS ok");
    const dbMs = Date.now() - t0;
    await ctx.tg.sendHtml(
      chatId,
      card(
        "💚 Tizim holati",
        ctx.cfg.BOT_VERSION,
        `• Runtime: <b>Cloudflare Workers (Edge)</b>\n` +
        `• D1 Database: <b>OK (${dbMs} ms)</b>\n` +
        `• Durable Objects (Guruh viktorina): <b>Faol</b>\n` +
        `• Gemini API kalit: <b>${ctx.cfg.GEMINI_API_KEY ? "Sozlangan ✅" : "Yo'q ❌"}</b>`
      )
    );
    return true;
  }
  return false;
}

export async function handleAdminState(ctx, chatId, uid, st, text) {
  if (st.action === "adm_broadcast") {
    await ctx.db.setState(uid, "adm_broadcast_confirm", { text });
    await ctx.tg.sendHtml(
      chatId,
      `<b>Ko'rinishi:</b>\n━━━━━━━━━━━━━━━\n${text}\n━━━━━━━━━━━━━━━\nHammaga yuborilsinmi?`,
      confirmKb("adm:broadcast_go", "adm:menu")
    );
    return true;
  }
  if (st.action === "adm_ch_post") {
    await ctx.db.clearState(uid);
    await ctx.tg.sendHtml(ctx.cfg.CHANNEL_USERNAME, text);
    await ctx.tg.sendHtml(chatId, "✅ Post kanalga joylandi!");
    return true;
  }
  if (st.action === "adm_ch_test") {
    await ctx.db.clearState(uid);
    const w = await ctx.tg.sendHtml(chatId, "⏳ Kanal testi tuzilmoqda...");
    try {
      const qs = await generateQuiz(ctx.cfg, `O'zbek tili va adabiyotidan "${text}" mavzusida test.`, 10);
      const tid = await ctx.db.addChannelTest(text, qs, 30);
      const link = `https://t.me/${ctx.cfg.BOT_USERNAME}?start=chtest_${tid}`;
      await ctx.tg.sendHtml(
        ctx.cfg.CHANNEL_USERNAME,
        card(
          `📝 Yangi onlayn test · ${esc(text)}`,
          "10 ta savol · natijangiz darhol jadvalga tushadi",
          "Quyidagi tugma orqali botga o'tib testni ishlang:"
        ),
        { inline_keyboard: [[{ text: "🎯 Testni boshlash", url: link }]] }
      );
      await ctx.tg.editHtml(chatId, w.message_id, `✅ Test #${tid} kanalga joylandi!`);
    } catch (e) {
      await ctx.tg.editHtml(chatId, w.message_id, `⚠️ ${esc(e.message)}`);
    }
    return true;
  }
  return false;
}

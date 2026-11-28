import { tashkentDate } from "../config.js";
import { esc, card } from "../textfmt.js";
import { BADGES, levelFor, levelLine } from "../levels.js";
import { sampleQuestions } from "../bank.js";
import { generateQuiz } from "../ai.js";
import { startQuiz } from "./quiz.js";
import { ratingTabs, profileKb, classMenu, btn } from "../keyboards.js";

const MEDALS = ["🥇", "🥈", "🥉"];

function buildCertificateSvg(name, levelName, levelEmoji, points, tests, accuracy, dateStr) {
  const safeName = esc(name).slice(0, 32);
  const safeLvl = esc(`${levelEmoji} ${levelName}`);
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f2537"/>
      <stop offset="100%" stop-color="#1b435d"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#d4af37"/>
      <stop offset="50%" stop-color="#f5d77f"/>
      <stop offset="100%" stop-color="#c59b27"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="800" fill="url(#bg)"/>
  <rect x="36" y="36" width="1128" height="728" rx="18" fill="none" stroke="url(#gold)" stroke-width="4"/>
  <rect x="52" y="52" width="1096" height="696" rx="12" fill="none" stroke="url(#gold)" stroke-width="1.5" stroke-opacity="0.6"/>
  <text x="600" y="130" text-anchor="middle" fill="#f5d77f" font-family="Georgia, serif" font-size="24" letter-spacing="6">AI TILSHUNOS · O'ZBEK TILI VA ADABIYOTI PORTALI</text>
  <text x="600" y="210" text-anchor="middle" fill="#ffffff" font-family="Georgia, serif" font-size="60" font-weight="bold">SERTIFIKAT</text>
  <line x1="340" y1="240" x2="860" y2="240" stroke="url(#gold)" stroke-width="2"/>
  <text x="600" y="300" text-anchor="middle" fill="#cfdbe6" font-family="Arial, sans-serif" font-size="24">Ushbu sertifikat egasi:</text>
  <text x="600" y="375" text-anchor="middle" fill="#f5d77f" font-family="Georgia, serif" font-size="50" font-weight="bold">${safeName}</text>
  <text x="600" y="445" text-anchor="middle" fill="#e6eef5" font-family="Arial, sans-serif" font-size="24">O'zbek tili va adabiyoti fanidan bilim va ko'nikmalarini muvaffaqiyatli namoyish etib,</text>
  <text x="600" y="495" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="30" font-weight="bold">${safeLvl} darajasiga erishdi</text>
  <g font-family="Arial, sans-serif" font-size="22" fill="#d8e4ee">
    <text x="280" y="590" text-anchor="middle">Jami XP: ${points}</text>
    <text x="600" y="590" text-anchor="middle">Yechilgan testlar: ${tests}</text>
    <text x="920" y="590" text-anchor="middle">Aniqlik: ${accuracy}%</text>
  </g>
  <text x="140" y="700" fill="#9fb6c8" font-family="Arial, sans-serif" font-size="20">Sana: ${esc(dateStr)}</text>
  <text x="1060" y="700" text-anchor="end" fill="#f5d77f" font-family="Arial, sans-serif" font-size="20">@aitilshunosbot</text>
</svg>`;
}

export async function showRating(ctx, chatId, uid, period = "all", editMid = null) {
  let title, body;
  if (period === "points") {
    const rows = await ctx.db.all(
      "SELECT user_id, first_name, points, streak FROM users WHERE status != 'blocked' ORDER BY points DESC LIMIT 20"
    );
    title = "🏆 Umumiy XP ballar reytingi";
    body = rows.map((r, i) => {
      const m = i < 3 ? MEDALS[i] : `${i + 1}.`;
      const me = Number(r.user_id) === Number(uid) ? " ◀️" : "";
      return `${m} <b>${esc(r.first_name || "Foydalanuvchi")}</b> — <b>${r.points} XP</b> (🔥${r.streak || 0})${me}`;
    }).join("\n") || "<i>Hali ma'lumot yo'q</i>";
  } else {
    const labels = { all: "Umumiy", week: "Haftalik (7 kun)", month: "Oylik (30 kun)" };
    title = `🏆 Reyting · ${labels[period] || "Umumiy"}`;
    const rows = await ctx.db.leaderboard(period, 20);
    const [myRank, totalP] = await ctx.db.userRank(uid, period);
    const lines = rows.map((r, i) => {
      const m = i < 3 ? MEDALS[i] : `${i + 1}.`;
      const me = Number(r.user_id) === Number(uid) ? " ◀️" : "";
      return `${m} <b>${esc(r.name || "Foydalanuvchi")}</b> — <b>${r.correct}/${r.total}</b> (${r.tests} test)${me}`;
    });
    const myLine = myRank ? `\n\n📍 Sizning o'rningiz: <b>${myRank}/${totalP}</b>` : "";
    body = (lines.join("\n") || "<i>Hali test natijalari yo'q</i>") + myLine;
  }
  const text = card(title, "Eng faol va bilimdon tilshunoslar", body);
  if (editMid) await ctx.tg.editHtml(chatId, editMid, text, ratingTabs(period));
  else await ctx.tg.sendHtml(chatId, text, ratingTabs(period));
}

export async function showProfile(ctx, chatId, user, editMid = null) {
  const uid = user.id;
  await ctx.db.ensureUser(uid, user.username, user.first_name);
  const u = await ctx.db.getUser(uid);
  const st = await ctx.db.userStats(uid);
  const badges = await ctx.db.getBadges(uid);
  const mistakes = await ctx.db.countMistakes(uid);
  const acc = st.total ? Math.round((100 * st.correct) / st.total) : 0;

  let examLine = "";
  if (u?.exam_date) {
    const diff = Math.ceil((new Date(u.exam_date) - new Date(tashkentDate())) / 86400000);
    const dTxt = diff > 0 ? `<b>${diff} kun</b> qoldi` : diff === 0 ? "<b>BUGUN!</b>" : "o'tib ketgan";
    examLine = `\n📅 Imtihon (${esc(u.exam_name || "Milliy sertifikat")}): ${u.exam_date} (${dTxt})`;
  }

  const body =
    `${levelLine(Number(u?.points || 0))}\n\n` +
    `🔥 Seriya: <b>${u?.streak || 0} kun</b> (rekord: ${u?.best_streak || 0})\n` +
    `📝 Yechilgan testlar: <b>${st.tests} ta</b> (${st.correct}/${st.total} · ${acc}%)\n` +
    `🔁 Xatolar banki: <b>${mistakes} ta</b>\n` +
    `🏅 Yutuqlar: <b>${badges.length}/${Object.keys(BADGES).length}</b>\n` +
    `🤝 Taklif qilingan do'stlar: <b>${u?.invites || 0} ta</b>${examLine}`;

  const text = card(`👤 ${esc(ctx.displayName(user))}`, `ID: ${uid}`, body);
  const kb = profileKb(Boolean(u?.reminders ?? 1), Boolean(u?.quiz_alerts ?? 0));
  if (editMid) await ctx.tg.editHtml(chatId, editMid, text, kb);
  else await ctx.tg.sendHtml(chatId, text, kb);
}

export async function handleProfileCallback(ctx, cq, data) {
  const uid = cq.from.id;
  const chatId = cq.message.chat.id;
  const mid = cq.message.message_id;

  if (data === "prof:badges") {
    const got = new Set(await ctx.db.getBadges(uid));
    const lines = Object.entries(BADGES).map(([code, [em, title, desc]]) => {
      const mark = got.has(code) ? "✅" : "🔒";
      return `${mark} ${em} <b>${title}</b> — <i>${desc}</i>`;
    });
    await ctx.tg.editHtml(
      chatId,
      mid,
      card("🏅 Yutuqlar (Badges)", `${got.size}/${Object.keys(BADGES).length} ochilgan`, lines.join("\n")),
      { inline_keyboard: [[btn("🔙 Profilga qaytish", "prof:back")]] }
    );
    return true;
  }
  if (data === "prof:back") {
    await showProfile(ctx, chatId, cq.from, mid);
    return true;
  }
  if (data === "prof:exam") {
    await ctx.db.setState(uid, "await_exam", {});
    await ctx.tg.sendHtml(
      chatId,
      "📅 <b>Imtihon sanasini yuboring</b> quyidagi formatda:\n" +
      "<code>2026-05-20 Milliy sertifikat</code>\n<i>(Sana YYYY-MM-DD ko'rinishida bo'lsin)</i>"
    );
    return true;
  }
  if (data === "prof:invite") {
    const link = `https://t.me/${ctx.cfg.BOT_USERNAME}?start=ref_${uid}`;
    await ctx.tg.sendHtml(
      chatId,
      card(
        "🤝 Do'stingizni taklif qiling",
        "Har bir yangi do'st uchun +30 XP",
        `Shaxsiy havolangiz:\n<code>${link}</code>\n\n` +
        "Do'stingiz shu havola orqali botga kirsa, ikkalangizga ham <b>+30 XP</b> beriladi!"
      )
    );
    return true;
  }
  if (data === "prof:rem_toggle") {
    const u = await ctx.db.getUser(uid);
    const next = !(u?.reminders ?? 1);
    await ctx.db.setReminders(uid, next);
    await showProfile(ctx, chatId, cq.from, mid);
    return true;
  }
  if (data === "prof:qalert_toggle") {
    const u = await ctx.db.getUser(uid);
    const next = !(u?.quiz_alerts ?? 0);
    await ctx.db.setQuizAlerts(uid, next);
    await showProfile(ctx, chatId, cq.from, mid);
    return true;
  }
  if (data === "prof:cert") {
    const u = await ctx.db.getUser(uid);
    const st = await ctx.db.userStats(uid);
    const pts = Number(u?.points || 0);
    const [cur] = levelFor(pts);
    const acc = st.total ? Math.round((100 * st.correct) / st.total) : 0;
    const svg = buildCertificateSvg(ctx.displayName(cq.from), cur[1], cur[2], pts, st.tests, acc, tashkentDate());
    await ctx.tg.sendPhotoSvgOrPng(chatId, svg, `sertifikat_${uid}.svg`, "📜 Shaxsiy yutuq sertifikatingiz!");
    return true;
  }
  if (data === "prof:class") {
    const tcls = await ctx.db.teacherClasses(uid);
    await ctx.tg.editHtml(
      chatId,
      mid,
      card("🏫 Sinf va o'quv guruhlari", "O'qituvchi va o'quvchilar uchun", "Sinf oching yoki ustozingiz bergan kod bilan qo'shiling:"),
      classMenu(tcls.length > 0)
    );
    return true;
  }
  return false;
}

export async function handleClassCallback(ctx, cq, data) {
  const uid = cq.from.id;
  const chatId = cq.message.chat.id;
  const mid = cq.message.message_id;
  const parts = data.split(":");
  const sub = parts[1];

  if (sub === "create") {
    await ctx.db.setState(uid, "await_class_name", {});
    await ctx.tg.sendHtml(chatId, "🏫 <b>Yangi sinf nomini yozing</b> (masalan: <i>11-A ona tili</i>):");
    return true;
  }
  if (sub === "join") {
    await ctx.db.setState(uid, "await_class_code", {});
    await ctx.tg.sendHtml(chatId, "🔑 <b>Sinf kodini yuboring</b> (6 belgili kod):");
    return true;
  }
  if (sub === "my") {
    const rows = await ctx.db.teacherClasses(uid);
    if (!rows.length) {
      await ctx.tg.sendHtml(chatId, "Sizda hali yaratilgan sinflar yo'q.");
      return true;
    }
    const kb = {
      inline_keyboard: rows.map(r => [btn(`${r.name} (${r.members} o'quvchi) · ${r.code}`, `cls:open:${r.code}`)]),
    };
    await ctx.tg.editHtml(chatId, mid, "📋 <b>Mening sinflarim:</b>", kb);
    return true;
  }
  if (sub === "joined") {
    const rows = await ctx.db.studentClasses(uid);
    if (!rows.length) {
      await ctx.tg.sendHtml(chatId, "Siz hali birorta sinfga qo'shilmagansiz.");
      return true;
    }
    const kb = {
      inline_keyboard: rows.map(r => [btn(`${r.name} (${r.code})`, `cls:st:${r.code}`)]),
    };
    await ctx.tg.editHtml(chatId, mid, "🎓 <b>A'zo sinflarim:</b>", kb);
    return true;
  }
  if (sub === "open") {
    const code = parts[2];
    const cls = await ctx.db.getClass(code);
    if (!cls || Number(cls.teacher_id) !== Number(uid)) return true;
    const members = await ctx.db.classMembers(code);
    const tests = await ctx.db.classTests(code, 5);
    const testBtns = tests.map(t => [btn(`📊 Natijalar: ${t.title}`, `cls:res:${t.id}`)]);
    await ctx.tg.editHtml(
      chatId,
      mid,
      card(
        `🏫 ${esc(cls.name)}`,
        `Kod: ${code} · O'quvchilar: ${members.length} ta`,
        `O'quvchilar qo'shilishi uchun kod: <code>${code}</code>\n` +
        `Yoki havola: <code>https://t.me/${ctx.cfg.BOT_USERNAME}?start=cls_${code}</code>`
      ),
      {
        inline_keyboard: [
          [btn("➕ Bazadan test berish (10 savol)", `cls:addbank:${code}`)],
          [btn("🤖 AI mavzudan test berish", `cls:addai:${code}`)],
          ...testBtns,
          [btn("🔙 Orqaga", "cls:my")],
        ],
      }
    );
    return true;
  }
  if (sub === "addbank") {
    const code = parts[2];
    const qs = sampleQuestions(null, 10);
    const tid = await ctx.db.addClassTest(code, `Sinf testi #${tashkentDate()}`, qs);
    const members = await ctx.db.classMembers(code);
    for (const m of members) {
      try {
        await ctx.tg.sendHtml(
          m.user_id,
          `📝 <b>Sinfingizda yangi test!</b>\nTestni ishlash uchun tugmani bosing:`,
          { inline_keyboard: [[btn("▶️ Testni boshlash", `cls:take:${tid}`)]] }
        );
      } catch {}
    }
    await ctx.tg.sendHtml(chatId, `✅ Test yaratildi va <b>${members.length} ta</b> o'quvchiga yuborildi!`);
    return true;
  }
  if (sub === "addai") {
    const code = parts[2];
    await ctx.db.setState(uid, "await_class_ai", { code });
    await ctx.tg.sendHtml(chatId, "🤖 Sinf testi uchun <b>mavzuni yozing</b> (masalan: <i>Sifat so'z turkumi</i>):");
    return true;
  }
  if (sub === "st") {
    const code = parts[2];
    const cls = await ctx.db.getClass(code);
    const tests = await ctx.db.classTests(code, 5);
    const kb = {
      inline_keyboard: tests.map(t => [btn(`▶️ ${t.title}`, `cls:take:${t.id}`)]),
    };
    await ctx.tg.editHtml(
      chatId,
      mid,
      card(`🎓 ${esc(cls?.name || code)}`, `Sinf kodi: ${code}`, tests.length ? "Mavjud testlar:" : "Hali test berilmagan."),
      kb
    );
    return true;
  }
  if (sub === "take") {
    const tid = Number(parts[2]);
    if (await ctx.db.hasClassResult(tid, uid)) {
      await ctx.tg.sendHtml(chatId, "✅ Siz bu sinf testini allaqachon ishlagansiz.");
      return true;
    }
    const t = await ctx.db.getClassTest(tid);
    if (!t) return true;
    await startQuiz(ctx, chatId, cq.from, t.questions, "class", t.title, "q_quick", 0, { test_id: tid });
    return true;
  }
  if (sub === "res") {
    const tid = Number(parts[2]);
    const rows = await ctx.db.classTestResults(tid);
    const lines = rows.map((r, i) => `${i + 1}. <b>${esc(r.name)}</b> — ${r.correct}/${r.total} (${r.duration}s)`);
    await ctx.tg.sendHtml(chatId, card("📊 Sinf testi natijalari", `Test #${tid}`, lines.join("\n") || "Hali hech kim ishlamadi."));
    return true;
  }
  return false;
}

export async function createAiClassTest(ctx, chatId, uid, code, topic) {
  if (!await ctx.checkAiGuard(uid, chatId, topic)) return;
  const w = await ctx.tg.sendHtml(chatId, "⏳ AI sinf testi tuzilmoqda...");
  try {
    const qs = await generateQuiz(ctx.cfg, `O'zbek tili va adabiyotidan "${topic}" mavzusida maktab sinf testi.`, 10);
    const tid = await ctx.db.addClassTest(code, topic, qs);
    const members = await ctx.db.classMembers(code);
    for (const m of members) {
      try {
        await ctx.tg.sendHtml(
          m.user_id,
          `📝 <b>Yangi sinf testi:</b> ${esc(topic)}`,
          { inline_keyboard: [[btn("▶️ Testni boshlash", `cls:take:${tid}`)]] }
        );
      } catch {}
    }
    await ctx.tg.editHtml(chatId, w.message_id, `✅ «${esc(topic)}» testi yaratildi va <b>${members.length} ta</b> o'quvchiga yuborildi!`);
  } catch (e) {
    await ctx.tg.editHtml(chatId, w.message_id, `⚠️ ${esc(e.message)}`);
  }
}

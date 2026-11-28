import { sampleQuestions, SECTIONS, sectionCounts, totalCount, questionKey, dailyQuestion } from "../bank.js";
import { generateQuiz, AIError, OffTopic } from "../ai.js";
import { esc, card, bar } from "../textfmt.js";
import { badgeTitle } from "../levels.js";
import { quizMenu, sectionsKb, countKb, quizControl, quizResultKb, certMenu, btn } from "../keyboards.js";

const LETTER = ["A", "B", "C", "D"];

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export async function openQuizMenu(ctx, chatId, editMid = null) {
  const txt = card(
    "🎯 Test va Viktorina",
    `Bazadagi tayyor savollar: ${totalCount()} ta · AI cheksiz mavzu`,
    "Rejimni tanlang:\n" +
    "• <b>Tezkor test</b> — aralash 10 savol\n" +
    "• <b>Bo'lim bo'yicha</b> — imlo, morfologiya, sintaksis...\n" +
    "• <b>AI mavzu</b> — istalgan mavzuda yangi savollar\n" +
    "• <b>Matn asosida</b> — matningizdan test tuzadi\n" +
    "• <b>Do'st bilan bellashuv</b> — bitta testda kim tez va aniq!\n" +
    "• <b>Imtihon rejimi</b> — 25 savol · 20 daqiqa"
  );
  if (editMid) await ctx.tg.editHtml(chatId, editMid, txt, quizMenu());
  else await ctx.tg.sendHtml(chatId, txt, quizMenu());
}

export async function startQuiz(ctx, chatId, user, questions, mode, title, retryCb = "q_quick", timeLimitSec = 0, meta = {}) {
  if (!questions || !questions.length) {
    await ctx.tg.sendHtml(chatId, "⚠️ Savollar topilmadi. Boshqa bo'lim yoki mavzuni sinab ko'ring.");
    return;
  }
  const session = {
    mode,
    title,
    retry_cb: retryCb,
    questions,
    idx: 0,
    correct: 0,
    started: Date.now() / 1000,
    time_limit: timeLimitSec,
    cur_correct: 0,
    cur_opts: [],
    meta,
  };
  await ctx.db.setState(user.id, "quiz", session);
  await sendQuestion(ctx, chatId, user.id, session);
}

export async function sendQuestion(ctx, chatId, uid, s) {
  if (s.time_limit && (Date.now() / 1000 - s.started) > s.time_limit) {
    await ctx.tg.sendHtml(chatId, "⌛ <b>Ajratilgan vaqt tugadi!</b>");
    await finishQuiz(ctx, chatId, uid, s);
    return;
  }
  if (s.idx >= s.questions.length) {
    await finishQuiz(ctx, chatId, uid, s);
    return;
  }

  const q = s.questions[s.idx];
  const order = shuffle([0, 1, 2, 3]);
  s.cur_opts = order.map(i => q.options[i]);
  s.cur_correct = order.indexOf(q.correct_option_id);

  let timerNote = "";
  if (s.time_limit) {
    const left = Math.max(0, Math.round(s.time_limit - (Date.now() / 1000 - s.started)));
    timerNote = ` · ⏱ ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  }

  const optsText = s.cur_opts.map((o, i) => `<b>${LETTER[i]})</b> ${esc(o)}`).join("\n");
  const text =
    `<b>Savol ${s.idx + 1}/${s.questions.length}</b>  ${bar(s.idx, s.questions.length, 8)}${timerNote}\n` +
    `<i>${esc(s.title)}</i>\n\n` +
    `${esc(q.question)}\n\n${optsText}`;

  const ansRow = LETTER.map((ltr, i) => btn(ltr, `q_ans:${s.mode}:${s.idx}:${i}`));
  const ctrl = quizControl(s.mode, s.idx, s.questions.length);
  const markup = { inline_keyboard: [ansRow, ...ctrl.inline_keyboard] };

  await ctx.db.setState(uid, "quiz", s);
  await ctx.tg.sendHtml(chatId, text, markup);
}

export async function handleAnswer(ctx, chatId, messageId, user, mode, idx, chosen) {
  const st = await ctx.db.getState(user.id, 3600);
  if (!st || st.action !== "quiz") return false;
  const s = st.data;
  if (s.mode !== mode || s.idx !== idx) return false;

  const q = s.questions[idx];
  const qk = questionKey(q);
  const ok = chosen === s.cur_correct;
  const chosenTxt = s.cur_opts[chosen] || "?";
  const rightTxt = s.cur_opts[s.cur_correct] || "?";

  let verdict;
  if (ok) {
    s.correct += 1;
    verdict = `✅ <b>To'g'ri!</b> (${LETTER[chosen]}) ${esc(chosenTxt)}`;
    if (s.mode === "mistakes" && await ctx.db.removeMistake(user.id, qk)) {
      const fixed = await ctx.db.kvIncr(`fixed:${user.id}`, 1);
      if (fixed >= 10 && await ctx.db.awardBadge(user.id, "mistake_fixer")) {
        await ctx.tg.sendHtml(chatId, "🏅 Yangi yutuq: <b>🛠 Xato tuzatuvchi</b>!");
      }
    }
  } else {
    verdict = `❌ <b>Xato.</b> Siz: (${LETTER[chosen]}) ${esc(chosenTxt)}\n✔️ To'g'ri javob: <b>(${LETTER[s.cur_correct]}) ${esc(rightTxt)}</b>`;
    await ctx.db.addMistake(user.id, qk, q);
  }

  const expl = q.explanation ? `\n\n💡 <i>${esc(q.explanation)}</i>` : "";
  await ctx.tg.editHtml(
    chatId,
    messageId,
    `<b>Savol ${idx + 1}/${s.questions.length}</b> · <i>${esc(s.title)}</i>\n\n${esc(q.question)}\n\n${verdict}${expl}`
  );

  s.idx += 1;
  await sendQuestion(ctx, chatId, user.id, s);
  return true;
}

export async function handleQuizSkip(ctx, chatId, messageId, uid, mode, idx) {
  const st = await ctx.db.getState(uid, 3600);
  if (!st || st.action !== "quiz" || st.data.mode !== mode || st.data.idx !== idx) return false;
  const s = st.data;
  const q = s.questions[idx];
  const rightTxt = s.cur_opts[s.cur_correct] || "?";
  await ctx.db.addMistake(uid, questionKey(q), q);
  await ctx.tg.editHtml(
    chatId,
    messageId,
    `⏭ <b>O'tkazib yuborildi</b> (${idx + 1}/${s.questions.length})\n` +
    `✔️ To'g'ri javob: <b>(${LETTER[s.cur_correct]}) ${esc(rightTxt)}</b>`
  );
  s.idx += 1;
  await sendQuestion(ctx, chatId, uid, s);
  return true;
}

export async function handleQuizHint(ctx, cbId, uid, mode, idx) {
  const st = await ctx.db.getState(uid, 3600);
  if (!st || st.action !== "quiz" || st.data.mode !== mode || st.data.idx !== idx) {
    await ctx.tg.answerCallback(cbId, "Bu savol uchun izoh mavjud emas.");
    return;
  }
  const q = st.data.questions[idx];
  const hint = q.explanation || `To'g'ri javob ${LETTER[st.data.cur_correct]} variant atrofida.`;
  await ctx.tg.answerCallback(cbId, hint.slice(0, 195), true);
}

export async function handleQuizStop(ctx, chatId, uid, mode) {
  const st = await ctx.db.getState(uid, 3600);
  if (!st || st.action !== "quiz" || st.data.mode !== mode) return;
  const s = st.data;
  s.questions = s.questions.slice(0, Math.max(1, s.idx));
  await finishQuiz(ctx, chatId, uid, s);
}

export async function finishQuiz(ctx, chatId, uid, s) {
  await ctx.db.clearState(uid);
  const total = s.questions.length;
  const cor = s.correct;
  const dur = Math.round((Date.now() / 1000 - s.started) * 10) / 10;
  const pct = total ? Math.round((100 * cor) / total) : 0;
  const user = await ctx.db.getUser(uid);
  const name = user?.first_name || `User ${uid}`;

  await ctx.db.recordResult(uid, name, s.mode, s.title, cor, total, dur);
  let xp = cor * 5 + (pct === 100 && total >= 5 ? 25 : 0);
  if (s.mode === "daily" && cor === 1) {
    await ctx.db.markDailyDone(uid);
    xp += 15;
    const dcnt = await ctx.db.kvIncr(`daily_cnt:${uid}`, 1);
    if (dcnt >= 7) await ctx.db.awardBadge(uid, "daily_7");
  }
  const totalPts = await ctx.db.addPoints(uid, xp);

  const earned = [];
  const stats = await ctx.db.userStats(uid);
  if (stats.tests >= 1 && await ctx.db.awardBadge(uid, "first_test")) earned.push(badgeTitle("first_test"));
  if (pct === 100 && total >= 5 && await ctx.db.awardBadge(uid, "perfect")) earned.push(badgeTitle("perfect"));
  if (stats.total >= 100 && await ctx.db.awardBadge(uid, "marathon")) earned.push(badgeTitle("marathon"));

  let extraNote = "";
  const meta = s.meta || {};
  if (s.mode === "class" && meta.test_id) {
    await ctx.db.saveClassResult(meta.test_id, uid, name, cor, total, dur);
    extraNote = "\n🏫 Natijangiz sinf jurnaliga yozildi.";
  } else if (s.mode === "channel" && meta.tid) {
    await ctx.db.saveChannelResult(meta.tid, uid, name, cor, total, dur);
    const rk = await ctx.db.channelRank(meta.tid, uid);
    const cnt = await ctx.db.channelCount(meta.tid);
    if (rk) extraNote = `\n📣 Kanal testi jadvalida o'rningiz: <b>${rk.rank}/${cnt}</b>`;
  } else if (s.mode === "duel" && meta.duel_id) {
    extraNote = await resolveDuel(ctx, meta.duel_id, uid, name, cor, total, dur);
  }

  let grade;
  if (pct >= 90) grade = "🌟 A'lo natija!";
  else if (pct >= 75) grade = "👏 Yaxshi natija!";
  else if (pct >= 50) grade = "👍 Qoniqarli, yana mashq qiling.";
  else grade = "📖 Mavzuni qayta ko'rib chiqing.";

  const badgesLine = earned.length ? `\n🏅 Yangi yutuq: <b>${earned.join(", ")}</b>` : "";
  const body =
    `${grade}\n\n` +
    `✅ To'g'ri: <b>${cor}/${total}</b> (${pct}%)\n` +
    `⏱ Vaqt: <b>${dur} soniya</b>\n` +
    `✨ Qo'shilgan XP: <b>+${xp}</b> (Jami: <b>${totalPts}</b>)` +
    `${badgesLine}${extraNote}`;
  const mistakesLeft = (await ctx.db.countMistakes(uid)) > 0;
  await ctx.tg.sendHtml(
    chatId,
    card("🏁 Test yakunlandi", esc(s.title), body),
    quizResultKb(s.retry_cb, mistakesLeft)
  );
}

async function resolveDuel(ctx, duelId, uid, name, cor, total, dur) {
  const pend = await ctx.db.getPending(`duel:${duelId}`);
  if (!pend) return "";
  const d = pend.payload;
  d.results[String(uid)] = { name, correct: cor, total, duration: dur };
  await ctx.db.savePending(`duel:${duelId}`, "duel", d);
  const ids = Object.keys(d.results);
  if (ids.length < 2) {
    return "\n⚔️ Raqibingiz testni yakunlashi kutilmoqda — natija ikkalangizga yuboriladi.";
  }
  const [u1, u2] = ids;
  const r1 = d.results[u1], r2 = d.results[u2];
  let winUid = null;
  if (r1.correct > r2.correct || (r1.correct === r2.correct && r1.duration < r2.duration)) winUid = u1;
  else if (r2.correct > r1.correct || (r2.correct === r1.correct && r2.duration < r1.duration)) winUid = u2;

  if (winUid) {
    await ctx.db.addPoints(winUid, 30);
    await ctx.db.awardBadge(winUid, "duelist");
  }
  const summary = card(
    "⚔️ Bellashuv yakunlandi!",
    esc(d.title),
    `1. <b>${esc(r1.name)}</b> — ${r1.correct}/${r1.total} (${r1.duration}s)\n` +
    `2. <b>${esc(r2.name)}</b> — ${r2.correct}/${r2.total} (${r2.duration}s)\n\n` +
    (winUid ? `🏆 G'olib: <b>${esc(d.results[winUid].name)}</b> (+30 XP)!` : "🤝 Durang!")
  );
  for (const target of [u1, u2]) {
    if (String(target) !== String(uid)) {
      try { await ctx.tg.sendHtml(target, summary); } catch {}
    }
  }
  await ctx.db.delPending(`duel:${duelId}`);
  return "\n\n" + summary;
}

export async function handleQuizCallback(ctx, cq, data) {
  const uid = cq.from.id;
  const chatId = cq.message.chat.id;
  const mid = cq.message.message_id;

  if (data === "q_back") {
    await openQuizMenu(ctx, chatId, mid);
    return true;
  }
  if (data === "q_quick") {
    await startQuiz(ctx, chatId, cq.from, sampleQuestions(null, 10), "quick", "Tezkor aralash test", "q_quick");
    return true;
  }
  if (data === "q_exam") {
    await startQuiz(ctx, chatId, cq.from, sampleQuestions(null, 25), "exam", "Imtihon rejimi (25 savol)", "q_exam", 20 * 60);
    return true;
  }
  if (data === "q_sections") {
    await ctx.tg.editHtml(chatId, mid, "📚 <b>Bo'limni tanlang:</b>", sectionsKb(SECTIONS, sectionCounts()));
    return true;
  }
  if (data.startsWith("q_sec:")) {
    const idx = Number(data.split(":")[1]);
    const sec = SECTIONS[idx];
    await ctx.tg.editHtml(chatId, mid, `📚 Bo'lim: <b>${esc(sec)}</b>\nSavollar sonini tanlang:`, countKb(`q_seccnt:${idx}`));
    return true;
  }
  if (data.startsWith("q_seccnt:")) {
    const [, idxS, cntS] = data.split(":");
    const sec = SECTIONS[Number(idxS)];
    const cnt = Number(cntS);
    await startQuiz(ctx, chatId, cq.from, sampleQuestions(sec, cnt), "section", sec, `q_seccnt:${idxS}:${cnt}`);
    return true;
  }
  if (data === "q_ai_topic") {
    await ctx.db.setState(uid, "await_ai_topic", {});
    await ctx.tg.sendHtml(
      chatId,
      "🤖 <b>Mavzuni yozing</b> (masalan: <i>Fe'l nisbatlari</i>, <i>Qo'shma gap</i>, <i>Alisher Navoiy hayoti</i>):"
    );
    return true;
  }
  if (data.startsWith("q_aicnt:")) {
    const cnt = Number(data.split(":")[1]);
    const st = await ctx.db.getState(uid, 900);
    const topic = st?.data?.topic || "Ona tili";
    await ctx.db.clearState(uid);
    if (!await ctx.checkAiGuard(uid, chatId, topic)) return true;
    const waitMsg = await ctx.tg.sendHtml(chatId, `⏳ <b>${esc(topic)}</b> mavzusida ${cnt} ta savol tuzilmoqda...`);
    try {
      const qs = await generateQuiz(ctx.cfg, `O'zbek tili va adabiyotidan "${topic}" mavzusida test.`, cnt);
      await ctx.tg.deleteMessage(chatId, waitMsg.message_id);
      await startQuiz(ctx, chatId, cq.from, qs, "ai", topic, "q_ai_topic");
    } catch (e) {
      await ctx.tg.editHtml(chatId, waitMsg.message_id, e instanceof OffTopic ? "⚠️ Faqat til va adabiyot mavzulari." : `⚠️ Xatolik: ${esc(e.message)}`);
    }
    return true;
  }
  if (data === "q_ai_text") {
    await ctx.db.setState(uid, "await_ai_passage", {});
    await ctx.tg.sendHtml(chatId, "📄 <b>Matn yuboring</b> (100–4000 belgi). Shu matn asosida 5 ta o'qish savodxonligi savoli tuzaman.");
    return true;
  }
  if (data === "q_duel") {
    const duelId = Math.random().toString(36).slice(2, 10);
    const qs = sampleQuestions(null, 7);
    await ctx.db.savePending(`duel:${duelId}`, "duel", {
      title: "Do'stlar bellashuvi (7 savol)",
      questions: qs,
      creator: uid,
      results: {},
    });
    const link = `https://t.me/${ctx.cfg.BOT_USERNAME}?start=duel_${duelId}`;
    await ctx.tg.sendHtml(
      chatId,
      card(
        "⚔️ Do'st bilan bellashuv",
        "7 savol · eng ko'p to'g'ri va tez javob bergan yutadi",
        `Quyidagi havolani do'stingizga yuboring:\n<code>${link}</code>\n\n` +
        "O'zingiz ham hozir boshlashingiz mumkin — raqibingiz tugatgach natija solishtiriladi!",
        "<i>G'olibga +30 XP!</i>"
      ),
      { inline_keyboard: [[btn("▶️ O'zim boshlash", `duel_go:${duelId}`)]] }
    );
    return true;
  }
  if (data.startsWith("duel_go:")) {
    const duelId = data.split(":")[1];
    const pend = await ctx.db.getPending(`duel:${duelId}`);
    if (!pend) {
      await ctx.tg.sendHtml(chatId, "⌛ Bellashuv muddati tugagan.");
      return true;
    }
    await startQuiz(ctx, chatId, cq.from, pend.payload.questions, "duel", pend.payload.title, "q_duel", 0, { duel_id: duelId });
    return true;
  }
  if (data === "q_group_help") {
    await ctx.tg.sendHtml(
      chatId,
      card(
        "👥 Guruhda viktorina",
        "Jonli ko'p o'yinchili musobaqa",
        "1. Botni Telegram guruhingizga qo'shing\n" +
        "2. Guruhda <code>/quiz</code> buyrug'ini yuboring\n" +
        "3. Kamida 2 ishtirokchi qo'shilgach <b>Boshlash</b> ni bosing!\n\n" +
        "<i>Tez javob va ketma-ket seriya uchun qo'shimcha ball beriladi.</i>"
      )
    );
    return true;
  }
  if (data.startsWith("q_ans:")) {
    const [, mode, idxS, optS] = data.split(":");
    await handleAnswer(ctx, chatId, mid, cq.from, mode, Number(idxS), Number(optS));
    return true;
  }
  if (data.startsWith("q_skip:")) {
    const [, mode, idxS] = data.split(":");
    await handleQuizSkip(ctx, chatId, mid, uid, mode, Number(idxS));
    return true;
  }
  if (data.startsWith("q_hint:")) {
    const [, mode, idxS] = data.split(":");
    await handleQuizHint(ctx, cq.id, uid, mode, Number(idxS));
    return true;
  }
  if (data.startsWith("q_stop:")) {
    const mode = data.split(":")[1];
    await handleQuizStop(ctx, chatId, uid, mode);
    return true;
  }
  if (data === "mistakes_start") {
    const ms = await ctx.db.getMistakes(uid, 15);
    if (!ms.length) {
      await ctx.tg.sendHtml(chatId, "🎉 Sizda tuzatilmagan xatolar yo'q!");
      return true;
    }
    await startQuiz(ctx, chatId, cq.from, ms, "mistakes", `Xatolar ustida ishlash (${ms.length} ta)`, "mistakes_start");
    return true;
  }
  if (data === "daily_start") {
    const q = dailyQuestion();
    await startQuiz(ctx, chatId, cq.from, q ? [q] : [], "daily", "Kun savoli", "daily_start");
    return true;
  }
  return false;
}

export async function openCertMenu(ctx, chatId, editMid = null) {
  const txt = card(
    "🎓 Milliy sertifikat tayyorgarligi",
    "BMB (DTM) standartiga mos simulyatsiya",
    "• <b>Full Mock</b> — 25 savol (til me'yorlari + adabiyot), 30 daqiqa\n" +
    "• <b>O'qish savodxonligi</b> — AI badiiy/ilmiy matn va 5 savol\n" +
    "• <b>Til me'yorlari</b> — imlo, punktuatsiya, morfologiya, sintaksis\n" +
    "• <b>Adabiyot</b> — 5–11-sinf darsliklari asosida\n" +
    "• <b>Esse</b> — 24 ballik mezon bo'yicha AI tekshiruvi"
  );
  if (editMid) await ctx.tg.editHtml(chatId, editMid, txt, certMenu());
  else await ctx.tg.sendHtml(chatId, txt, certMenu());
}

export async function handleCertCallback(ctx, cq, data) {
  const uid = cq.from.id;
  const chatId = cq.message.chat.id;
  const kind = data.split(":")[1];

  if (kind === "full") {
    await startQuiz(ctx, chatId, cq.from, sampleQuestions(null, 25), "cert_full", "Milliy sertifikat · Full Mock", "cert:full", 30 * 60);
    return true;
  }
  if (kind === "norms") {
    const norms = SECTIONS.filter(s => !s.toLowerCase().includes("adabiyot"));
    const sec = norms.length ? norms[Math.floor(Math.random() * norms.length)] : null;
    await startQuiz(ctx, chatId, cq.from, sampleQuestions(sec, 15), "cert_norms", "Til me'yorlari (15 savol)", "cert:norms");
    return true;
  }
  if (kind === "lit") {
    const litSec = SECTIONS.find(s => s.toLowerCase().includes("adabiyot")) || null;
    await startQuiz(ctx, chatId, cq.from, sampleQuestions(litSec, 15), "cert_lit", "Adabiyot (15 savol)", "cert:lit");
    return true;
  }
  if (kind === "reading") {
    if (!await ctx.checkAiGuard(uid, chatId, "o'qish savodxonligi")) return true;
    const waitMsg = await ctx.tg.sendHtml(chatId, "⏳ O'qish savodxonligi matni va 5 ta savol tayyorlanmoqda...");
    try {
      const qs = await generateQuiz(
        ctx.cfg,
        "O'zbek tilida 180-220 so'zli ilmiy-ommabop yoki badiiy-publitsistik kichik matn yarating va " +
        "birinchi savol matnida shu matnni to'liq keltiring, qolgan 4 savol ham shu matn tahliliga oid bo'lsin " +
        "(Milliy sertifikat o'qish savodxonligi darajasida).",
        5
      );
      await ctx.tg.deleteMessage(chatId, waitMsg.message_id);
      await startQuiz(ctx, chatId, cq.from, qs, "cert_read", "O'qish savodxonligi (AI)", "cert:reading");
    } catch (e) {
      await ctx.tg.editHtml(chatId, waitMsg.message_id, `⚠️ Xatolik: ${esc(e.message)}`);
    }
    return true;
  }
  if (kind === "essay") {
    await ctx.db.setState(uid, "await_essay", {});
    await ctx.tg.sendHtml(chatId, "✍️ <b>Esseni matn yoki rasm ko'rinishida yuboring</b> — 24 ballik mezon asosida tekshiraman.");
    return true;
  }
  return false;
}

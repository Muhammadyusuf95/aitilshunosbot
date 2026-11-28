import { dailyQuestion, totalCount } from "./bank.js";
import { generateText, OffTopic } from "./ai.js";
import { esc, card } from "./textfmt.js";
import {
  mainMenu, MENU_BUTTONS, BTN_QUIZ, BTN_CERT, BTN_DAILY, BTN_MISTAKES,
  BTN_ESSAY, BTN_RESEARCH, BTN_TRANSLIT, BTN_TOOLS, BTN_RATING, BTN_PROFILE,
  countKb, btn,
} from "./keyboards.js";
import { openQuizMenu, handleQuizCallback, openCertMenu, handleCertCallback, startQuiz } from "./handlers/quiz.js";
import {
  openEssayMenu, handleEssayCallback, runEssayReview,
  openResearchMenu, handleResearchCallback, runResearch,
  openTranslitMenu, handleTranslitCallback, runTranslit,
  openToolsMenu, handleToolCallback, runTool,
} from "./handlers/ai_tools.js";
import { showRating, showProfile, handleProfileCallback, handleClassCallback, createAiClassTest } from "./handlers/social.js";
import { openAdminMenu, handleAdminCallback, handleAdminState } from "./handlers/admin.js";
import { handleGroupQuizCmd, handleGroupCallback, handlePollAnswer } from "./handlers/group.js";

const LETTER = ["A", "B", "C", "D"];

export async function handleUpdate(ctx, update) {
  if (update.poll_answer) {
    await handlePollAnswer(ctx, update.poll_answer);
    return;
  }
  if (update.callback_query) {
    await onCallback(ctx, update.callback_query);
    return;
  }
  const msg = update.message;
  if (!msg || !msg.from) return;

  const chatType = msg.chat?.type;
  if (chatType === "group" || chatType === "supergroup") {
    const txt = msg.text || "";
    if (/^\/quiz(?:@|\s|$)/i.test(txt)) {
      await handleGroupQuizCmd(ctx, msg);
    }
    return;
  }
  if (chatType !== "private") return;

  await onPrivateMessage(ctx, msg);
}

async function onPrivateMessage(ctx, msg) {
  const user = msg.from;
  const uid = user.id;
  const chatId = msg.chat.id;
  const text = (msg.text || msg.caption || "").trim();

  await ctx.touchAndNotify(user, chatId);

  if (text.startsWith("/start")) {
    await ctx.db.clearState(uid);
    const arg = text.split(/\s+/)[1] || "";

    if (arg.startsWith("ref_")) {
      const inviter = Number(arg.slice(4));
      if (inviter && await ctx.db.registerReferral(uid, inviter, 30)) {
        await ctx.db.awardBadge(inviter, "inviter");
        await ctx.tg.sendHtml(chatId, "🎁 Do'stingiz taklifi orqali kirdingiz — <b>+30 XP</b> bonus!");
        try { await ctx.tg.sendHtml(inviter, `🤝 Do'stingiz <b>${esc(user.first_name)}</b> botga qo'shildi! <b>+30 XP</b>!`); } catch {}
      }
    }

    if (!await ctx.ensureSub(uid, chatId, user)) return;

    if (arg === "daily") {
      const q = dailyQuestion();
      await startQuiz(ctx, chatId, user, q ? [q] : [], "daily", "Kun savoli", "daily_start");
      return;
    }
    if (arg.startsWith("duel_")) {
      const duelId = arg.slice(5);
      const pend = await ctx.db.getPending(`duel:${duelId}`);
      if (!pend) {
        await ctx.tg.sendHtml(chatId, "⌛ Bellashuv havolasi eskirgan.");
      } else {
        await startQuiz(ctx, chatId, user, pend.payload.questions, "duel", pend.payload.title, "q_duel", 0, { duel_id: duelId });
        return;
      }
    }
    if (arg.startsWith("cls_")) {
      const code = arg.slice(4).toUpperCase();
      const cls = await ctx.db.getClass(code);
      if (cls && await ctx.db.joinClass(code, uid, ctx.displayName(user))) {
        await ctx.tg.sendHtml(chatId, `🏫 Siz <b>${esc(cls.name)}</b> sinfiga qo'shildingiz!`);
      }
    }
    if (arg.startsWith("chtest_")) {
      const tid = Number(arg.slice(7));
      const t = await ctx.db.getChannelTest(tid);
      if (t) {
        await startQuiz(ctx, chatId, user, t.questions, "channel", t.title, "q_quick", 0, { tid });
        return;
      }
    }

    await sendWelcome(ctx, chatId, user);
    return;
  }

  if (text === "/admin" && ctx.isAdmin(uid)) {
    await ctx.db.clearState(uid);
    await openAdminMenu(ctx, chatId);
    return;
  }

  if (text === "/help") {
    await sendWelcome(ctx, chatId, user);
    return;
  }

  if (!await ctx.ensureSub(uid, chatId, user)) return;

  if (MENU_BUTTONS.has(text)) {
    await ctx.db.clearState(uid);
    if (text === BTN_QUIZ) return openQuizMenu(ctx, chatId);
    if (text === BTN_CERT) return openCertMenu(ctx, chatId);
    if (text === BTN_DAILY) return openDailyQuestion(ctx, chatId, uid);
    if (text === BTN_MISTAKES) return openMistakes(ctx, chatId, uid);
    if (text === BTN_ESSAY) return openEssayMenu(ctx, chatId);
    if (text === BTN_RESEARCH) return openResearchMenu(ctx, chatId);
    if (text === BTN_TRANSLIT) return openTranslitMenu(ctx, chatId, uid);
    if (text === BTN_TOOLS) return openToolsMenu(ctx, chatId);
    if (text === BTN_RATING) return showRating(ctx, chatId, uid, "all");
    if (text === BTN_PROFILE) return showProfile(ctx, chatId, user);
  }

  const st = await ctx.db.getState(uid, 1800);
  if (st && st.action !== "quiz") {
    if (await handleAdminState(ctx, chatId, uid, st, text)) return;

    if (st.action === "await_ai_topic" && text) {
      await ctx.db.setState(uid, "await_ai_topic_cnt", { topic: text.slice(0, 120) });
      await ctx.tg.sendHtml(chatId, `🤖 Mavzu: <b>${esc(text)}</b>\nSavollar sonini tanlang:`, countKb("q_aicnt"));
      return;
    }
    if (st.action === "await_ai_passage" && text) {
      await ctx.db.clearState(uid);
      if (text.length < 80) {
        await ctx.tg.sendHtml(chatId, "⚠️ Matn juda qisqa (kamida 80 belgi bo'lsin).");
        return;
      }
      if (!await ctx.checkAiGuard(uid, chatId, text)) return;
      const w = await ctx.tg.sendHtml(chatId, "⏳ Matn asosida 5 ta savol tuzilmoqda...");
      const { generateQuiz } = await import("./ai.js");
      try {
        const qs = await generateQuiz(ctx.cfg, "Matnni tushunish va tahlil qilish bo'yicha 5 ta savol tuzing.", 5, null, text);
        await ctx.tg.deleteMessage(chatId, w.message_id);
        await startQuiz(ctx, chatId, user, qs, "passage", "Matn asosida test", "q_ai_text");
      } catch (e) {
        await ctx.tg.editHtml(chatId, w.message_id, `⚠️ ${esc(e.message)}`);
      }
      return;
    }
    if (st.action === "await_essay") {
      const photo = msg.photo ? msg.photo[msg.photo.length - 1].file_id : null;
      if (!photo && text.length < 40) {
        await ctx.tg.sendHtml(chatId, "⚠️ Esse matni kamida 40 belgidan iborat bo'lsin yoki daftar rasmini yuboring.");
        return;
      }
      await ctx.db.clearState(uid);
      await runEssayReview(ctx, chatId, uid, text, photo);
      return;
    }
    if (st.action === "await_research" && text) {
      await ctx.db.clearState(uid);
      await runResearch(ctx, chatId, uid, st.data.kind, text);
      return;
    }
    if (st.action === "await_translit" && text) {
      await runTranslit(ctx, chatId, uid, text, st.data.mode);
      return;
    }
    if (st.action === "await_tool" && text) {
      await ctx.db.clearState(uid);
      await runTool(ctx, chatId, uid, st.data.kind, text);
      return;
    }
    if (st.action === "await_exam" && text) {
      const m = text.match(/^(\d{4}-\d{2}-\d{2})(?:\s+(.+))?$/);
      if (!m) {
        await ctx.tg.sendHtml(chatId, "⚠️ Format noto'g'ri. Namuna: <code>2026-05-20 Milliy sertifikat</code>");
        return;
      }
      await ctx.db.clearState(uid);
      await ctx.db.setExam(uid, (m[2] || "Milliy sertifikat").slice(0, 60), m[1]);
      await ctx.tg.sendHtml(chatId, `✅ Imtihon sanasi saqlandi: <b>${m[1]}</b> (${esc(m[2] || "Milliy sertifikat")})`);
      return;
    }
    if (st.action === "await_class_name" && text) {
      await ctx.db.clearState(uid);
      const code = Math.random().toString(36).slice(2, 8).toUpperCase();
      await ctx.db.createClass(code, uid, text);
      await ctx.tg.sendHtml(
        chatId,
        card(
          "✅ Yangi sinf ochildi!",
          esc(text),
          `Sinf kodi: <code>${code}</code>\n` +
          `O'quvchilar uchun tezkor havola:\n<code>https://t.me/${ctx.cfg.BOT_USERNAME}?start=cls_${code}</code>`
        )
      );
      return;
    }
    if (st.action === "await_class_code" && text) {
      await ctx.db.clearState(uid);
      const code = text.toUpperCase().replace(/[^A-Z0-9]/g, "");
      const cls = await ctx.db.getClass(code);
      if (!cls) {
        await ctx.tg.sendHtml(chatId, "❌ Bunday kodli sinf topilmadi.");
        return;
      }
      await ctx.db.joinClass(code, uid, ctx.displayName(user));
      await ctx.tg.sendHtml(chatId, `🎓 Siz <b>${esc(cls.name)}</b> sinfiga muvaffaqiyatli qo'shildingiz!`);
      return;
    }
    if (st.action === "await_class_ai" && text) {
      await ctx.db.clearState(uid);
      await createAiClassTest(ctx, chatId, uid, st.data.code, text);
      return;
    }
  }

  if (text) {
    if (!await ctx.checkAiGuard(uid, chatId, text)) return;
    await ctx.tg.sendChatAction(chatId, "typing");
    try {
      const ans = await generateText(ctx.cfg, text, 0.3);
      await ctx.tg.sendLong(chatId, ans, mainMenu());
    } catch (e) {
      await ctx.tg.sendHtml(
        chatId,
        e instanceof OffTopic
          ? "⚠️ Men faqat <b>o'zbek tili, adabiyot va filologiya</b> bo'yicha savollarga javob beraman."
          : `⚠️ ${esc(e.message)}`
      );
    }
  }
}

async function onCallback(ctx, cq) {
  const data = cq.data || "";
  const uid = cq.from.id;
  const chatId = cq.message?.chat?.id;
  const chatType = cq.message?.chat?.type;

  if (chatType === "group" || chatType === "supergroup") {
    if (data.startsWith("gq_")) {
      await handleGroupCallback(ctx, cq, data);
    }
    return;
  }

  await ctx.tg.answerCallback(cq.id);

  if (data === "check_sub") {
    if (await ctx.ensureSub(uid, chatId, cq.from, cq.id)) {
      await ctx.tg.deleteMessage(chatId, cq.message.message_id);
      await sendWelcome(ctx, chatId, cq.from);
    }
    return;
  }

  if (!await ctx.ensureSub(uid, chatId, cq.from)) return;

  if (data === "cancel") {
    await ctx.db.clearState(uid);
    await ctx.tg.editHtml(chatId, cq.message.message_id, "❌ Bekor qilindi.");
    return;
  }
  if (data.startsWith("rating:")) {
    await showRating(ctx, chatId, uid, data.split(":")[1], cq.message.message_id);
    return;
  }
  if (data.startsWith("prof:")) {
    await handleProfileCallback(ctx, cq, data);
    return;
  }
  if (data.startsWith("cls:")) {
    await handleClassCallback(ctx, cq, data);
    return;
  }
  if (data.startsWith("adm:")) {
    await handleAdminCallback(ctx, cq, data);
    return;
  }
  if (data.startsWith("cert:")) {
    await handleCertCallback(ctx, cq, data);
    return;
  }
  if (data.startsWith("essay:")) {
    await handleEssayCallback(ctx, cq, data);
    return;
  }
  if (data.startsWith("res:")) {
    await handleResearchCallback(ctx, cq, data);
    return;
  }
  if (data.startsWith("tr_")) {
    await handleTranslitCallback(ctx, cq, data);
    return;
  }
  if (data.startsWith("tool:")) {
    await handleToolCallback(ctx, cq, data);
    return;
  }
  await handleQuizCallback(ctx, cq, data);
}

async function sendWelcome(ctx, chatId, user) {
  const txt = card(
    "🎓 AI Tilshunos — O'zbek tili va adabiyoti akademiyasi",
    `Xush kelibsiz, ${esc(user.first_name || "Do'st")}!`,
    `• 🎯 <b>Test va viktorinalar</b> (${totalCount()} ta bazaviy + cheksiz AI savollar)\n` +
    "• 🎓 <b>Milliy sertifikat</b> (Full Mock, o'qish savodxonligi, 24 ballik esse)\n" +
    "• 📚 <b>Ilmiy tadqiqot</b> (OAK/GOST adabiyotlar, annotatsiya, dissertatsiya rejasi)\n" +
    "• 🔤 <b>Alifbo o'girish</b> (Lotin ↔ Yangi alifbo Ö Ğ Ş Ç ↔ Kirill)\n" +
    "• 🛠 <b>Til vositalari</b> (imlo, morfologiya, sintaksis, aruz tahlili)\n\n" +
    "<i>Quyidagi menyudan bo'lim tanlang yoki to'g'ridan-to'g'ri savol yozing!</i>"
  );
  await ctx.tg.sendHtml(chatId, txt, mainMenu());
}

async function openDailyQuestion(ctx, chatId, uid) {
  const u = await ctx.db.getUser(uid);
  const q = dailyQuestion();
  if (!q) return;
  const opts = q.options.map((o, i) => `<b>${LETTER[i]})</b> ${esc(o)}`).join("\n");
  await ctx.tg.sendHtml(
    chatId,
    card(
      "📅 Bugungi kun savoli",
      esc(q.bolim || "Ona tili"),
      `${esc(q.question)}\n\n${opts}\n\n` +
      (u?.daily_done ? "<i>Bugungi kun savolini yechgansiz, qayta mashq qilishingiz mumkin.</i>" : "<i>To'g'ri javob uchun <b>+20 XP</b>!</i>")
    ),
    { inline_keyboard: [[btn("▶️ Javob berish", "daily_start")]] }
  );
}

async function openMistakes(ctx, chatId, uid) {
  const cnt = await ctx.db.countMistakes(uid);
  if (!cnt) {
    await ctx.tg.sendHtml(
      chatId,
      card("🔁 Xatolar ustida ishlash", "Xatolar banki bo'sh", "🎉 Sizda tuzatilmagan xato savollar yo'q! Yangi test yechib bilimingizni sinang.")
    );
    return;
  }
  await ctx.tg.sendHtml(
    chatId,
    card(
      "🔁 Xatolar ustida ishlash",
      `Saqlangan xatolar: ${cnt} ta`,
      "Testlarda xato javob bergan savollaringiz shu yerda yig'iladi. To'g'ri javob bersangiz ro'yxatdan o'chiriladi."
    ),
    { inline_keyboard: [[btn(`▶️ Xatolarni ishlash (${Math.min(15, cnt)} ta)`, "mistakes_start")]] }
  );
}

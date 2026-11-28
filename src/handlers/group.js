import { sampleQuestions } from "../bank.js";
import { generateQuiz } from "../ai.js";
import { esc, card } from "../textfmt.js";
import { groupLobbyKb } from "../keyboards.js";

function roomStub(env, chatId) {
  const id = env.QUIZ_ROOM.idFromName(String(chatId));
  return env.QUIZ_ROOM.get(id);
}

export async function handleGroupQuizCmd(ctx, msg) {
  const chatId = msg.chat.id;
  const user = msg.from;
  const stub = roomStub(ctx.env, chatId);

  const stRes = await stub.fetch("https://room/status");
  const st = await stRes.json();
  if (st.active) {
    await ctx.tg.sendHtml(chatId, "⚠️ Bu guruhda hozir viktorina jarayonda. Tugashini kuting yoki <code>/stopquiz</code> bosing.");
    return;
  }

  const rawArg = (msg.text || "").replace(/^\/quiz(?:@\w+)?\s*/i, "").trim();
  const topic = rawArg || "O'zbek tili va adabiyoti";
  let questions;
  if (rawArg) {
    if (!await ctx.checkAiGuard(user.id, chatId, rawArg)) return;
    const w = await ctx.tg.sendHtml(chatId, `⏳ <b>${esc(rawArg)}</b> mavzusida 10 ta savol tuzilmoqda...`);
    try {
      questions = await generateQuiz(ctx.cfg, `O'zbek tili va adabiyotidan "${rawArg}" mavzusida guruh viktorinasi.`, 10);
      await ctx.tg.deleteMessage(chatId, w.message_id);
    } catch (e) {
      await ctx.tg.editHtml(chatId, w.message_id, `⚠️ ${esc(e.message)}`);
      return;
    }
  } else {
    questions = sampleQuestions(null, 10);
  }

  if (!questions || !questions.length) {
    await ctx.tg.sendHtml(chatId, "⚠️ Savollar tayyorlanmadi.");
    return;
  }

  const lobbyId = Math.random().toString(36).slice(2, 10);
  const creatorName = ctx.displayName(user);
  const mins = Math.floor(ctx.cfg.LOBBY_TTL_SEC / 60);
  const lobbyText = card(
    `🏆 Guruh viktorinasi · ${esc(topic)}`,
    `${questions.length} savol · 20 soniya`,
    `<b>Ishtirokchilar (1):</b>\n• ${esc(creatorName)}\n\n` +
    `<i>Kamida <b>${ctx.cfg.MIN_PLAYERS} ta</b> o'yinchi kerak · ${mins} daqiqa ichida boshlanadi.</i>`
  );
  const sent = await ctx.tg.sendHtml(chatId, lobbyText, groupLobbyKb(lobbyId, ctx.cfg.MIN_PLAYERS, 1));

  const session = {
    id: lobbyId,
    chat_id: chatId,
    creator: user.id,
    topic,
    questions,
    per_sec: 20,
    phase: "lobby",
    created_at: Date.now() / 1000,
    warned: false,
    lobby_msg: sent.message_id,
    players: { [String(user.id)]: creatorName },
    scores: { [String(user.id)]: 0 },
    times: { [String(user.id)]: 0.0 },
    correct_cnt: { [String(user.id)]: 0 },
    streak: { [String(user.id)]: 0 },
    idx: -1,
    cur_poll_id: null,
    cur_correct: 0,
    cur_answers: {},
    cur_started: 0,
    silent_streak: 0,
  };
  await stub.fetch("https://room/create", {
    method: "POST",
    body: JSON.stringify({ session }),
  });
}

export async function handleGroupCallback(ctx, cq, data) {
  const chatId = cq.message.chat.id;
  const uid = cq.from.id;
  const [action, lobbyId] = data.split(":");
  const cmdMap = {
    gq_join: "join",
    gq_start: "start",
    gq_cancel: "cancel",
    gq_pause: "pause",
    gq_resume: "resume",
    gq_stop: "stop",
  };
  const ep = cmdMap[action];
  if (!ep) return false;

  const stub = roomStub(ctx.env, chatId);
  const res = await stub.fetch(`https://room/${ep}`, {
    method: "POST",
    body: JSON.stringify({
      lobbyId,
      userId: uid,
      name: ctx.displayName(cq.from),
      isAdmin: ctx.isAdmin(uid),
    }),
  });
  const out = await res.json().catch(() => ({ ok: false }));
  if (!out.ok && out.msg) {
    await ctx.tg.answerCallback(cq.id, out.msg, true);
  } else {
    await ctx.tg.answerCallback(cq.id);
  }
  return true;
}

export async function handlePollAnswer(ctx, pa) {
  const chatId = await ctx.db.getPollChat(pa.poll_id);
  if (!chatId) return;
  const stub = roomStub(ctx.env, chatId);
  await stub.fetch("https://room/answer", {
    method: "POST",
    body: JSON.stringify({
      pollId: pa.poll_id,
      userId: pa.user?.id,
      name: ctx.displayName(pa.user),
      optionIds: pa.option_ids || [],
    }),
  });
}

import { TelegramClient } from "./telegram.js";
import { Database } from "./db.js";
import { getConfig } from "./config.js";
import { esc, card } from "./textfmt.js";
import { groupLobbyKb, groupQuizControl, groupPausedKb } from "./keyboards.js";

const LOBBY_WARN_BEFORE = 120;
const AUTO_PAUSE_SILENT = 3;
const LETTER = ["A", "B", "C", "D"];
const MEDALS = ["🥇", "🥈", "🥉"];

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export class QuizRoom {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.cfg = getConfig(env);
    this.tg = new TelegramClient(this.cfg.TELEGRAM_TOKEN);
    this.db = new Database(env.DB);
  }

  async getSession() {
    return (await this.state.storage.get("session")) || null;
  }

  async saveSession(s) {
    await this.state.storage.put("session", s);
  }

  async clearSession() {
    await this.state.storage.delete("session");
    await this.state.storage.deleteAlarm();
  }

  async setAlarmAfter(sec) {
    await this.state.storage.setAlarm(Date.now() + Math.max(1, sec) * 1000);
  }

  async fetch(request) {
    const url = new URL(request.url);
    const body = request.method === "POST" ? await request.json().catch(() => ({})) : {};
    const path = url.pathname;

    if (path === "/status") {
      const s = await this.getSession();
      if (!s) return Response.json({ active: false });
      const age = Date.now() / 1000 - s.created_at;
      if (s.phase === "lobby" && age > this.cfg.LOBBY_TTL_SEC) {
        await this.clearSession();
        return Response.json({ active: false });
      }
      return Response.json({ active: true, session: s });
    }

    if (path === "/create") {
      const s = body.session;
      await this.saveSession(s);
      const warnDelay = Math.max(15, this.cfg.LOBBY_TTL_SEC - LOBBY_WARN_BEFORE);
      await this.setAlarmAfter(warnDelay);
      return Response.json({ ok: true });
    }

    if (path === "/join") {
      const s = await this.getSession();
      if (!s || s.id !== body.lobbyId || s.phase !== "lobby") {
        return Response.json({ ok: false, msg: "Lobby tugagan." });
      }
      const uid = String(body.userId);
      if (uid in s.players) {
        return Response.json({ ok: false, msg: "Siz allaqachon ro'yxatdasiz." });
      }
      s.players[uid] = body.name;
      s.scores[uid] = 0;
      s.times[uid] = 0.0;
      s.correct_cnt[uid] = 0;
      s.streak[uid] = 0;
      await this.saveSession(s);
      await this.updateLobbyMessage(s);
      return Response.json({ ok: true, count: Object.keys(s.players).length });
    }

    if (path === "/start") {
      const s = await this.getSession();
      if (!s || s.id !== body.lobbyId || s.phase !== "lobby") {
        return Response.json({ ok: false, msg: "Lobby topilmadi." });
      }
      if (!body.isAdmin && String(body.userId) !== String(s.creator)) {
        return Response.json({ ok: false, msg: "Faqat tashkilotchi boshlay oladi." });
      }
      const n = Object.keys(s.players).length;
      if (n < this.cfg.MIN_PLAYERS) {
        return Response.json({
          ok: false,
          msg: `Viktorina boshlanishi uchun kamida ${this.cfg.MIN_PLAYERS} ta o'yinchi kerak (hozir ${n} ta).`,
        });
      }
      await this.beginQuiz(s);
      return Response.json({ ok: true });
    }

    if (path === "/cancel") {
      const s = await this.getSession();
      if (!s || s.id !== body.lobbyId) return Response.json({ ok: false, msg: "Topilmadi." });
      if (!body.isAdmin && String(body.userId) !== String(s.creator)) {
        return Response.json({ ok: false, msg: "Faqat tashkilotchi." });
      }
      await this.clearSession();
      await this.tg.editHtml(s.chat_id, s.lobby_msg, "❌ Viktorina bekor qilindi.");
      return Response.json({ ok: true });
    }

    if (path === "/pause") {
      const s = await this.getSession();
      if (!s || s.id !== body.lobbyId || s.phase !== "running") {
        return Response.json({ ok: false, msg: "Faol viktorina topilmadi." });
      }
      if (!body.isAdmin && String(body.userId) !== String(s.creator)) {
        return Response.json({ ok: false, msg: "Faqat tashkilotchi yoki admin." });
      }
      await this.pauseQuiz(s, "Tashkilotchi pauza qildi.");
      return Response.json({ ok: true });
    }

    if (path === "/resume") {
      const s = await this.getSession();
      if (!s || s.id !== body.lobbyId || s.phase !== "paused") {
        return Response.json({ ok: false, msg: "Pauzadagi viktorina topilmadi." });
      }
      if (!body.isAdmin && String(body.userId) !== String(s.creator)) {
        return Response.json({ ok: false, msg: "Faqat tashkilotchi yoki admin." });
      }
      s.phase = "running";
      s.silent_streak = 0;
      await this.saveSession(s);
      await this.tg.sendHtml(s.chat_id, "▶️ <b>Viktorina davom etmoqda!</b>");
      await this.sendNextQuestion(s);
      return Response.json({ ok: true });
    }

    if (path === "/stop") {
      const s = await this.getSession();
      if (!s || s.id !== body.lobbyId) return Response.json({ ok: false, msg: "Topilmadi." });
      if (!body.isAdmin && String(body.userId) !== String(s.creator)) {
        return Response.json({ ok: false, msg: "Faqat tashkilotchi yoki admin." });
      }
      await this.finishQuiz(s, true);
      return Response.json({ ok: true });
    }

    if (path === "/answer") {
      const s = await this.getSession();
      if (!s || s.phase !== "running" || s.cur_poll_id !== String(body.pollId)) {
        return Response.json({ ok: false });
      }
      const uid = String(body.userId);
      if (uid in s.cur_answers) return Response.json({ ok: false });
      if (!(uid in s.players)) {
        s.players[uid] = body.name || `User ${uid}`;
        s.scores[uid] = 0;
        s.times[uid] = 0.0;
        s.correct_cnt[uid] = 0;
        s.streak[uid] = 0;
      }
      const elapsed = Math.min(s.per_sec, Math.max(0.1, Date.now() / 1000 - s.cur_started));
      const opt = Array.isArray(body.optionIds) && body.optionIds.length ? Number(body.optionIds[0]) : -1;
      s.cur_answers[uid] = [opt, elapsed];
      await this.saveSession(s);
      if (Object.keys(s.cur_answers).length >= Object.keys(s.players).length) {
        await this.resolveQuestion(s);
      }
      return Response.json({ ok: true });
    }

    return new Response("Not found", { status: 404 });
  }

  async updateLobbyMessage(s) {
    const names = Object.values(s.players).map(n => `• ${esc(n)}`).join("\n") || "<i>Hali hech kim qo'shilmadi</i>";
    const mins = Math.floor(this.cfg.LOBBY_TTL_SEC / 60);
    const txt = card(
      `🏆 Guruh viktorinasi · ${esc(s.topic)}`,
      `${s.questions.length} savol · ${s.per_sec} soniya`,
      `<b>Ishtirokchilar (${Object.keys(s.players).length}):</b>\n${names}\n\n` +
      `<i>Kamida <b>${this.cfg.MIN_PLAYERS} ta</b> o'yinchi kerak · ${mins} daqiqa ichida boshlanadi.</i>`
    );
    await this.tg.editHtml(
      s.chat_id,
      s.lobby_msg,
      txt,
      groupLobbyKb(s.id, this.cfg.MIN_PLAYERS, Object.keys(s.players).length)
    );
  }

  async beginQuiz(s) {
    s.phase = "running";
    s.idx = -1;
    s.silent_streak = 0;
    await this.saveSession(s);
    await this.tg.editReplyMarkup(s.chat_id, s.lobby_msg, null);
    await this.tg.sendHtml(
      s.chat_id,
      `🚀 <b>Viktorina boshlandi!</b>\nIshtirokchilar: <b>${Object.keys(s.players).length}</b> · Savollar: <b>${s.questions.length}</b>`
    );
    await this.sendNextQuestion(s);
  }

  async sendNextQuestion(s) {
    s.idx += 1;
    if (s.idx >= s.questions.length) {
      await this.finishQuiz(s, false);
      return;
    }
    const q = s.questions[s.idx];
    const order = shuffle([0, 1, 2, 3]);
    const opts = order.map(i => q.options[i]);
    const correctIdx = order.indexOf(q.correct_option_id);

    const pollMsg = await this.tg.sendPoll(
      s.chat_id,
      `[${s.idx + 1}/${s.questions.length}] ${q.question}`,
      opts,
      {
        type: "quiz",
        correct_option_id: correctIdx,
        is_anonymous: false,
        open_period: Math.max(5, Math.min(600, s.per_sec)),
        explanation: (q.explanation || "").slice(0, 200),
      }
    );
    s.cur_poll_id = String(pollMsg.poll.id);
    s.cur_correct = correctIdx;
    s.cur_answers = {};
    s.cur_started = Date.now() / 1000;
    await this.saveSession(s);
    await this.db.mapPoll(s.cur_poll_id, s.chat_id);

    if (s.idx === 0) {
      await this.tg.sendHtml(s.chat_id, "⚙️ <i>Boshqaruv:</i>", groupQuizControl(s.id));
    }
    await this.setAlarmAfter(s.per_sec + 1.5);
  }

  async resolveQuestion(s) {
    const q = s.questions[s.idx];
    const answered = Object.keys(s.cur_answers).length;
    if (answered === 0) {
      s.silent_streak += 1;
    } else {
      s.silent_streak = 0;
    }

    const roundLines = [];
    for (const [uid, name] of Object.entries(s.players)) {
      const ans = s.cur_answers[uid];
      if (!ans) {
        s.streak[uid] = 0;
        continue;
      }
      const [opt, elapsed] = ans;
      s.times[uid] = (s.times[uid] || 0) + elapsed;
      if (opt === s.cur_correct) {
        s.streak[uid] = (s.streak[uid] || 0) + 1;
        s.correct_cnt[uid] = (s.correct_cnt[uid] || 0) + 1;
        const speedBonus = Math.round(500 * Math.max(0, s.per_sec - elapsed) / s.per_sec);
        const streakBonus = 100 * Math.max(0, s.streak[uid] - 1);
        const pts = 1000 + speedBonus + streakBonus;
        s.scores[uid] = (s.scores[uid] || 0) + pts;
        const st = s.streak[uid] >= 2 ? ` 🔥×${s.streak[uid]}` : "";
        roundLines.push(`✅ ${esc(name)}: <b>+${pts}</b> (${elapsed.toFixed(1)}s)${st}`);
      } else {
        s.streak[uid] = 0;
        roundLines.push(`❌ ${esc(name)}`);
      }
    }

    const order = Object.keys(s.players).sort(
      (a, b) => (s.scores[b] || 0) - (s.scores[a] || 0) || (s.times[a] || 0) - (s.times[b] || 0)
    );
    const board = order.slice(0, 5).map((u, idx) => {
      const m = idx < 3 ? MEDALS[idx] : `${idx + 1}.`;
      return `${m} ${esc(s.players[u])} — <b>${s.scores[u] || 0}</b>`;
    }).join("\n");
    const ansLetter = LETTER[s.cur_correct] || "?";
    const body =
      `To'g'ri javob: <b>${ansLetter}</b>\n` +
      (q.explanation ? `<i>💡 ${esc(q.explanation)}</i>\n` : "") +
      `\n${roundLines.length ? roundLines.join("\n") : "<i>Hech kim javob bermadi</i>"}\n\n` +
      `<b>Joriy jadval:</b>\n${board}`;

    s.cur_poll_id = null;
    await this.saveSession(s);
    await this.tg.sendHtml(s.chat_id, body);

    if (s.silent_streak >= AUTO_PAUSE_SILENT && s.idx + 1 < s.questions.length) {
      await this.pauseQuiz(s, `Ketma-ket ${AUTO_PAUSE_SILENT} ta savolga javob berilmadi.`);
      return;
    }
    await this.sendNextQuestion(s);
  }

  async pauseQuiz(s, reason) {
    s.phase = "paused";
    s.paused_at = Date.now() / 1000;
    s.cur_poll_id = null;
    await this.saveSession(s);
    await this.tg.sendHtml(
      s.chat_id,
      `⏸ <b>Viktorina pauzaga qo'yildi</b> (${s.idx + 1}/${s.questions.length}-savoldan keyin)\n` +
      `<i>Sabab: ${esc(reason)}\n${this.cfg.QUIZ_PAUSE_MAX_MIN} daqiqa davom ettirilmasa avtomatik tugatiladi.</i>`,
      groupPausedKb(s.id)
    );
    await this.setAlarmAfter(this.cfg.QUIZ_PAUSE_MAX_MIN * 60);
  }

  async finishQuiz(s, stopped) {
    const order = Object.keys(s.players).sort(
      (a, b) => (s.scores[b] || 0) - (s.scores[a] || 0) || (s.times[a] || 0) - (s.times[b] || 0)
    );
    const lines = [];
    for (let idx = 0; idx < order.length; idx++) {
      const uid = order[idx];
      const m = idx < 3 ? MEDALS[idx] : `${idx + 1}.`;
      const cor = s.correct_cnt[uid] || 0;
      lines.push(`${m} <b>${esc(s.players[uid])}</b> — <b>${s.scores[uid] || 0}</b> ball (${cor}/${s.questions.length})`);
      try {
        await this.db.recordResult(uid, s.players[uid], "group", s.topic, cor, s.questions.length, s.times[uid] || 0);
        await this.db.addPoints(uid, cor * 5 + (idx === 0 ? 30 : 0));
      } catch {}
    }
    const status = stopped ? "Viktorina muddatidan oldin yakunlandi" : "Viktorina yakunlandi!";
    await this.clearSession();
    await this.tg.sendHtml(
      s.chat_id,
      card(`🏆 ${status}`, esc(s.topic), lines.join("\n") || "Ishtirokchilar yo'q")
    );
  }

  async alarm() {
    const s = await this.getSession();
    if (!s) return;

    if (s.phase === "lobby") {
      const age = Date.now() / 1000 - s.created_at;
      if (!s.warned && age < this.cfg.LOBBY_TTL_SEC - 10) {
        s.warned = true;
        await this.saveSession(s);
        await this.tg.sendHtml(
          s.chat_id,
          `⏳ <b>Viktorina lobby 2 daqiqadan keyin yopiladi!</b>\n` +
          `Hozir <b>${Object.keys(s.players).length}/${this.cfg.MIN_PLAYERS}</b> o'yinchi tayyor.`
        );
        await this.setAlarmAfter(Math.max(10, this.cfg.LOBBY_TTL_SEC - age));
      } else {
        await this.clearSession();
        await this.tg.editHtml(
          s.chat_id,
          s.lobby_msg,
          `⌛ <b>Viktorina bekor qilindi</b> — ${Math.floor(this.cfg.LOBBY_TTL_SEC / 60)} daqiqa ichida kamida ` +
          `${this.cfg.MIN_PLAYERS} o'yinchi yig'ilmadi.`
        );
      }
      return;
    }

    if (s.phase === "running" && s.cur_poll_id) {
      await this.resolveQuestion(s);
      return;
    }

    if (s.phase === "paused") {
      await this.finishQuiz(s, true);
    }
  }
}

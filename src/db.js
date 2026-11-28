import { tashkentDate, utcNowStr } from "./config.js";

export class Database {
  constructor(d1) {
    this.db = d1;
  }

  async one(sql, params = []) {
    const stmt = this.db.prepare(sql).bind(...params);
    return (await stmt.first()) || null;
  }

  async all(sql, params = []) {
    const stmt = this.db.prepare(sql).bind(...params);
    const res = await stmt.all();
    return res.results || [];
  }

  async run(sql, params = []) {
    const stmt = this.db.prepare(sql).bind(...params);
    const res = await stmt.run();
    return res.meta?.changes || 0;
  }

  async getUser(uid) {
    return this.one("SELECT * FROM users WHERE user_id = ?", [Number(uid)]);
  }

  async ensureUser(uid, username = "", firstName = "") {
    await this.run(
      "INSERT INTO users (user_id, username, first_name, points, streak, best_streak, last_active, status) " +
      "VALUES (?, ?, ?, 0, 0, 0, '', 'active') ON CONFLICT (user_id) DO NOTHING",
      [Number(uid), username || "", firstName || ""]
    );
  }

  async touchUser(user, today = null) {
    today = today || tashkentDate();
    const yesterday = tashkentDate(-1);
    const uname = user.username || "";
    const fname = user.first_name || "";
    const row = await this.getUser(user.id);
    if (!row) {
      await this.run(
        "INSERT INTO users (user_id, username, first_name, points, streak, best_streak, last_active, status) " +
        "VALUES (?, ?, ?, 10, 1, 1, ?, 'active') ON CONFLICT (user_id) DO NOTHING",
        [Number(user.id), uname, fname, today]
      );
      return { streak: 1, gained: 10, broken: false, new_day: true, is_new_user: true, prev_streak: 0, points: 10 };
    }
    const last = row.last_active || "";
    let streak = Number(row.streak || 0);
    let points = Number(row.points || 0);
    if (last === today) {
      if (row.status === "blocked" || row.username !== uname || row.first_name !== fname) {
        await this.run(
          "UPDATE users SET username = ?, first_name = ?, status = 'active' WHERE user_id = ?",
          [uname, fname, Number(user.id)]
        );
      }
      return { streak, gained: 0, broken: false, new_day: false, is_new_user: false, prev_streak: streak, points };
    }
    const prev = streak;
    let broken = false;
    if (last === yesterday) {
      streak += 1;
    } else {
      broken = Boolean(last) && prev >= 2;
      streak = 1;
    }
    const gained = 10 + 3 * Math.min(streak - 1, 10);
    points += gained;
    const best = Math.max(Number(row.best_streak || 0), streak);
    await this.run(
      "UPDATE users SET username = ?, first_name = ?, points = ?, streak = ?, best_streak = ?, " +
      "last_active = ?, status = 'active' WHERE user_id = ?",
      [uname, fname, points, streak, best, today, Number(user.id)]
    );
    return { streak, gained, broken, new_day: true, is_new_user: false, prev_streak: prev, points };
  }

  async addPoints(uid, n) {
    await this.run("UPDATE users SET points = COALESCE(points, 0) + ? WHERE user_id = ?", [Number(n), Number(uid)]);
    const r = await this.one("SELECT points FROM users WHERE user_id = ?", [Number(uid)]);
    return Number(r?.points || 0);
  }

  async setStatus(uid, status) {
    await this.run("UPDATE users SET status = ? WHERE user_id = ?", [status, Number(uid)]);
  }

  async registerReferral(newUid, inviterUid, bonus = 30) {
    if (Number(newUid) === Number(inviterUid)) return false;
    const me = await this.getUser(newUid);
    const inviter = await this.getUser(inviterUid);
    if (!me || !inviter || me.referred_by) return false;
    await this.run("UPDATE users SET referred_by = ? WHERE user_id = ?", [Number(inviterUid), Number(newUid)]);
    await this.run(
      "UPDATE users SET invites = COALESCE(invites, 0) + 1, points = COALESCE(points, 0) + ? WHERE user_id = ?",
      [bonus, Number(inviterUid)]
    );
    await this.addPoints(newUid, bonus);
    return true;
  }

  async markDailyDone(uid, today = null) {
    await this.run("UPDATE users SET daily_done = ? WHERE user_id = ?", [today || tashkentDate(), Number(uid)]);
  }

  async recordResult(uid, name, mode, title, correct, total, duration) {
    await this.run(
      "INSERT INTO quiz_results (user_id, name, mode, title, correct, total, duration, created_at) " +
      "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
      [Number(uid), name, mode, String(title || "").slice(0, 120), Number(correct), Number(total), Number(duration), utcNowStr()]
    );
  }

  async leaderboard(period = "all", limit = 25) {
    const since = { week: 7, month: 30 }[period];
    const params = [];
    let where = "";
    if (since) {
      const cutoff = new Date(Date.now() - since * 86400 * 1000).toISOString().replace("T", " ").slice(0, 19);
      where = "WHERE r.created_at >= ?";
      params.push(cutoff);
    }
    params.push(Number(limit));
    return this.all(
      "SELECT r.user_id AS user_id, MAX(r.name) AS name, SUM(r.correct) AS correct, SUM(r.total) AS total, " +
      "COUNT(*) AS tests, SUM(r.duration) AS duration, MAX(u.points) AS points, MAX(u.streak) AS streak " +
      "FROM quiz_results r LEFT JOIN users u ON u.user_id = r.user_id " +
      `${where} GROUP BY r.user_id ORDER BY SUM(r.correct) DESC, SUM(r.duration) ASC LIMIT ?`,
      params
    );
  }

  async userRank(uid, period = "all") {
    const rows = await this.leaderboard(period, 5000);
    const idx = rows.findIndex(r => Number(r.user_id) === Number(uid));
    return idx >= 0 ? [idx + 1, rows.length] : [null, rows.length];
  }

  async userStats(uid) {
    const r = (await this.one(
      "SELECT COUNT(*) AS tests, COALESCE(SUM(correct), 0) AS correct, COALESCE(SUM(total), 0) AS total " +
      "FROM quiz_results WHERE user_id = ?",
      [Number(uid)]
    )) || {};
    const best = await this.one(
      "SELECT correct, total FROM quiz_results WHERE user_id = ? AND total >= 5 " +
      "ORDER BY (correct * 1.0 / total) DESC, total DESC LIMIT 1",
      [Number(uid)]
    );
    return {
      tests: Number(r.tests || 0),
      correct: Number(r.correct || 0),
      total: Number(r.total || 0),
      best,
    };
  }

  async summaryCounts() {
    const r = await this.one("SELECT COUNT(*) AS n, COUNT(DISTINCT user_id) AS p FROM quiz_results");
    return { tests: Number(r?.n || 0), participants: Number(r?.p || 0) };
  }

  async addMistake(uid, qkey, question) {
    await this.run(
      "INSERT INTO mistakes (user_id, qkey, payload, created_at) VALUES (?, ?, ?, ?) " +
      "ON CONFLICT (user_id, qkey) DO UPDATE SET payload = excluded.payload",
      [Number(uid), qkey, JSON.stringify(question), utcNowStr()]
    );
  }

  async removeMistake(uid, qkey) {
    return (await this.run("DELETE FROM mistakes WHERE user_id = ? AND qkey = ?", [Number(uid), qkey])) > 0;
  }

  async countMistakes(uid) {
    const r = await this.one("SELECT COUNT(*) AS n FROM mistakes WHERE user_id = ?", [Number(uid)]);
    return Number(r?.n || 0);
  }

  async getMistakes(uid, limit = 20) {
    const rows = await this.all(
      "SELECT payload FROM mistakes WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
      [Number(uid), Number(limit)]
    );
    const out = [];
    for (const r of rows) {
      try { out.push(JSON.parse(r.payload)); } catch {}
    }
    return out;
  }

  async awardBadge(uid, code) {
    const n = await this.run(
      "INSERT INTO badges (user_id, code, earned_at) VALUES (?, ?, ?) ON CONFLICT (user_id, code) DO NOTHING",
      [Number(uid), code, utcNowStr()]
    );
    return n > 0;
  }

  async getBadges(uid) {
    const rows = await this.all("SELECT code FROM badges WHERE user_id = ? ORDER BY earned_at", [Number(uid)]);
    return rows.map(r => r.code);
  }

  async kvGet(key, def = null) {
    const r = await this.one("SELECT v FROM kv WHERE k = ?", [key]);
    return r ? r.v : def;
  }

  async kvSet(key, val) {
    await this.run(
      "INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT (k) DO UPDATE SET v = excluded.v",
      [key, String(val)]
    );
  }

  async kvIncr(key, by = 1) {
    const n = Number((await this.kvGet(key, 0)) || 0) + by;
    await this.kvSet(key, n);
    return n;
  }

  async nextCounter(name) {
    return this.kvIncr(`counter:${name}`, 1);
  }

  async setState(uid, action, data = {}) {
    await this.run(
      "INSERT INTO user_states (user_id, action, data, ts) VALUES (?, ?, ?, ?) " +
      "ON CONFLICT (user_id) DO UPDATE SET action = excluded.action, data = excluded.data, ts = excluded.ts",
      [Number(uid), action, JSON.stringify(data), Math.floor(Date.now() / 1000)]
    );
  }

  async getState(uid, ttlSec = 1800) {
    const r = await this.one("SELECT action, data, ts FROM user_states WHERE user_id = ?", [Number(uid)]);
    if (!r) return null;
    if (Math.floor(Date.now() / 1000) - Number(r.ts) > ttlSec) {
      await this.clearState(uid);
      return null;
    }
    let data = {};
    try { data = JSON.parse(r.data || "{}"); } catch {}
    return { action: r.action, data, ts: Number(r.ts) };
  }

  async clearState(uid) {
    await this.run("DELETE FROM user_states WHERE user_id = ?", [Number(uid)]);
  }

  async savePending(id, kind, payload) {
    await this.run(
      "INSERT INTO pending_items (id, kind, payload, created_at) VALUES (?, ?, ?, ?) " +
      "ON CONFLICT (id) DO UPDATE SET kind = excluded.kind, payload = excluded.payload, created_at = excluded.created_at",
      [String(id), kind, JSON.stringify(payload), Math.floor(Date.now() / 1000)]
    );
  }

  async getPending(id, maxAgeSec = 86400) {
    const r = await this.one("SELECT kind, payload, created_at FROM pending_items WHERE id = ?", [String(id)]);
    if (!r) return null;
    if (Math.floor(Date.now() / 1000) - Number(r.created_at) > maxAgeSec) return null;
    try {
      return { kind: r.kind, payload: JSON.parse(r.payload) };
    } catch {
      return null;
    }
  }

  async delPending(id) {
    await this.run("DELETE FROM pending_items WHERE id = ?", [String(id)]);
  }

  async setExam(uid, name, dateStr) {
    await this.run("UPDATE users SET exam_name = ?, exam_date = ? WHERE user_id = ?", [name, dateStr, Number(uid)]);
  }

  async setReminders(uid, on) {
    await this.run("UPDATE users SET reminders = ? WHERE user_id = ?", [on ? 1 : 0, Number(uid)]);
  }

  async setQuizAlerts(uid, on) {
    await this.run("UPDATE users SET quiz_alerts = ? WHERE user_id = ?", [on ? 1 : 0, Number(uid)]);
  }

  async usersForQuizAlert() {
    return this.all("SELECT user_id, first_name FROM users WHERE status != 'blocked' AND COALESCE(quiz_alerts, 0) = 1");
  }

  async usersForReminder(dates) {
    const marks = dates.map(() => "?").join(",");
    return this.all(
      "SELECT user_id, first_name, streak, last_active, exam_name, exam_date FROM users " +
      `WHERE status != 'blocked' AND COALESCE(reminders, 1) = 1 AND last_active IN (${marks})`,
      dates
    );
  }

  async createClass(code, teacherId, name) {
    await this.run(
      "INSERT INTO classes (code, teacher_id, name, created_at) VALUES (?, ?, ?, ?)",
      [code, Number(teacherId), name.slice(0, 60), utcNowStr()]
    );
  }

  async getClass(code) {
    return this.one("SELECT * FROM classes WHERE code = ?", [code]);
  }

  async teacherClasses(teacherId) {
    return this.all(
      "SELECT c.code AS code, c.name AS name, (SELECT COUNT(*) FROM class_members m WHERE m.code = c.code) AS members " +
      "FROM classes c WHERE c.teacher_id = ? ORDER BY c.created_at DESC",
      [Number(teacherId)]
    );
  }

  async studentClasses(uid) {
    return this.all(
      "SELECT c.code AS code, c.name AS name FROM class_members m JOIN classes c ON c.code = m.code " +
      "WHERE m.user_id = ? ORDER BY m.joined_at DESC",
      [Number(uid)]
    );
  }

  async joinClass(code, uid, name) {
    return (await this.run(
      "INSERT INTO class_members (code, user_id, name, joined_at) VALUES (?, ?, ?, ?) " +
      "ON CONFLICT (code, user_id) DO NOTHING",
      [code, Number(uid), name, utcNowStr()]
    )) > 0;
  }

  async classMembers(code) {
    return this.all("SELECT user_id, name FROM class_members WHERE code = ? ORDER BY joined_at", [code]);
  }

  async addClassTest(code, title, questions) {
    await this.run(
      "INSERT INTO class_tests (code, title, questions, created_at) VALUES (?, ?, ?, ?)",
      [code, title.slice(0, 100), JSON.stringify(questions), utcNowStr()]
    );
    const r = await this.one("SELECT MAX(id) AS id FROM class_tests WHERE code = ?", [code]);
    return Number(r.id);
  }

  async getClassTest(testId) {
    const r = await this.one("SELECT * FROM class_tests WHERE id = ?", [Number(testId)]);
    if (r) r.questions = JSON.parse(r.questions);
    return r;
  }

  async classTests(code, limit = 5) {
    return this.all(
      "SELECT id, title, created_at FROM class_tests WHERE code = ? ORDER BY id DESC LIMIT ?",
      [code, Number(limit)]
    );
  }

  async saveClassResult(testId, uid, name, correct, total, duration) {
    return (await this.run(
      "INSERT INTO class_results (test_id, user_id, name, correct, total, duration, created_at) " +
      "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (test_id, user_id) DO NOTHING",
      [Number(testId), Number(uid), name, Number(correct), Number(total), Number(duration), utcNowStr()]
    )) > 0;
  }

  async classTestResults(testId) {
    return this.all(
      "SELECT user_id, name, correct, total, duration FROM class_results WHERE test_id = ? " +
      "ORDER BY correct DESC, duration ASC",
      [Number(testId)]
    );
  }

  async hasClassResult(testId, uid) {
    return Boolean(await this.one("SELECT 1 AS x FROM class_results WHERE test_id = ? AND user_id = ?", [Number(testId), Number(uid)]));
  }

  async addChannelTest(title, questions, duration) {
    await this.run(
      "INSERT INTO channel_tests (title, questions, duration, created_at) VALUES (?, ?, ?, ?)",
      [title.slice(0, 100), JSON.stringify(questions), Number(duration), utcNowStr()]
    );
    const r = await this.one("SELECT MAX(id) AS id FROM channel_tests");
    return Number(r.id);
  }

  async getChannelTest(tid) {
    const r = await this.one("SELECT * FROM channel_tests WHERE id = ?", [Number(tid)]);
    if (r) r.questions = JSON.parse(r.questions);
    return r;
  }

  async recentChannelTests(limit = 8) {
    return this.all("SELECT id, title, created_at FROM channel_tests ORDER BY id DESC LIMIT ?", [Number(limit)]);
  }

  async saveChannelResult(tid, uid, name, correct, total, duration) {
    return (await this.run(
      "INSERT INTO channel_results (test_id, user_id, name, correct, total, duration, created_at) " +
      "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (test_id, user_id) DO NOTHING",
      [Number(tid), Number(uid), name, Number(correct), Number(total), Number(duration), utcNowStr()]
    )) > 0;
  }

  async channelBoard(tid, limit = 10) {
    return this.all(
      "SELECT user_id, name, correct, total, duration FROM channel_results WHERE test_id = ? " +
      "ORDER BY correct DESC, duration ASC LIMIT ?",
      [Number(tid), Number(limit)]
    );
  }

  async channelCount(tid) {
    const r = await this.one("SELECT COUNT(*) AS n FROM channel_results WHERE test_id = ?", [Number(tid)]);
    return Number(r?.n || 0);
  }

  async channelRank(tid, uid) {
    const me = await this.one(
      "SELECT correct, duration FROM channel_results WHERE test_id = ? AND user_id = ?",
      [Number(tid), Number(uid)]
    );
    if (!me) return null;
    const better = await this.one(
      "SELECT COUNT(*) AS n FROM channel_results WHERE test_id = ? " +
      "AND (correct > ? OR (correct = ? AND duration < ?))",
      [Number(tid), me.correct, me.correct, me.duration]
    );
    return { rank: Number(better.n) + 1, correct: Number(me.correct), duration: Number(me.duration) };
  }

  async userCounts() {
    const total = Number((await this.one("SELECT COUNT(*) AS n FROM users"))?.n || 0);
    const blocked = Number((await this.one("SELECT COUNT(*) AS n FROM users WHERE status = 'blocked'"))?.n || 0);
    const today = Number((await this.one("SELECT COUNT(*) AS n FROM users WHERE last_active = ?", [tashkentDate()]))?.n || 0);
    const weekCut = tashkentDate(-6);
    const week = Number((await this.one("SELECT COUNT(*) AS n FROM users WHERE last_active >= ?", [weekCut]))?.n || 0);
    return { total, blocked, active: total - blocked, today, week };
  }

  async usersPage(page, perPage = 8) {
    return this.all(
      "SELECT user_id, username, first_name, points, streak, status FROM users " +
      "ORDER BY points DESC, user_id DESC LIMIT ? OFFSET ?",
      [Number(perPage), Number(page * perPage)]
    );
  }

  async allUserIds(onlyActive = true) {
    const sql = "SELECT user_id FROM users" + (onlyActive ? " WHERE status != 'blocked'" : "");
    return (await this.all(sql)).map(r => r.user_id);
  }

  async exportUsers() {
    return this.all(
      "SELECT user_id, username, first_name, points, streak, best_streak, status, last_active, invites " +
      "FROM users ORDER BY points DESC"
    );
  }

  async mapPoll(pollId, chatId) {
    await this.run(
      "INSERT INTO poll_map (poll_id, chat_id, created_at) VALUES (?, ?, ?) " +
      "ON CONFLICT (poll_id) DO UPDATE SET chat_id = excluded.chat_id, created_at = excluded.created_at",
      [String(pollId), String(chatId), Math.floor(Date.now() / 1000)]
    );
  }

  async getPollChat(pollId) {
    const r = await this.one("SELECT chat_id FROM poll_map WHERE poll_id = ?", [String(pollId)]);
    return r ? r.chat_id : null;
  }
}

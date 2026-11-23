"""Shaxsiy kabinet, reyting, nishonlar, do'st taklif qilish."""
from app import config, levels
from app.db import get_db
from app.handlers.common import on_cb
from app.runtime import answer_cb, bot, show
from app.textfmt import card, esc, send_html
from app.ui import kb, rank_btn


def _rank_line(uid):
    db = get_db()
    r_all, n_all = db.user_rank(uid, "all")
    r_week, n_week = db.user_rank(uid, "week")
    parts = []
    parts.append(f"#{r_all} / {n_all}" if r_all else "—")
    week = f"#{r_week} / {n_week}" if r_week else "—"
    return parts[0], week


def profile_view(user):
    db = get_db()
    row = db.get_user(user.id) or {}
    points = row.get("points") or 0
    streak = row.get("streak") or 0
    best_streak = max(row.get("best_streak") or 0, streak)
    stats = db.user_stats(user.id)
    acc = round(100 * stats["correct"] / stats["total"]) if stats["total"] else 0
    rank_all, rank_week = _rank_line(user.id)
    badges = db.get_badges(user.id)
    mistakes = db.count_mistakes(user.id)
    best = stats["best"]
    best_txt = f"{best['correct']}/{best['total']}" if best else "—"

    badge_line = "  ".join(levels.BADGES[c][0] for c in badges if c in levels.BADGES) or "<i>hali yo'q — test ishlab to'plang</i>"
    body = (
        f"<b>{esc(user.first_name or 'Foydalanuvchi')}</b>   <code>{user.id}</code>\n\n"
        f"{levels.level_line(points)}\n\n"
        f"🔥 Seriya: <b>{streak} kun</b>  (rekord: {best_streak})\n"
        f"📝 Testlar: <b>{stats['tests']}</b>  ·  Savollar: <b>{stats['total']}</b>\n"
        f"🎯 Aniqlik: <b>{acc}%</b>  ·  Eng yaxshi: <b>{best_txt}</b>\n"
        f"🏆 O'rin: <b>{rank_all}</b> (hafta: {rank_week})\n"
        f"🤝 Takliflar: <b>{row.get('invites') or 0}</b>\n\n"
        f"🏅 <b>Nishonlar:</b> {badge_line}"
    )
    rows = []
    if mistakes:
        rows.append([(f"🔁 Xatolar ustida ishlash ({mistakes})", "review:start")])
    rows.append([("🏅 Barcha nishonlar", "prof:badges"), ("🤝 Do'st taklif qilish", "prof:invite")])
    rows.append([rank_btn("🏆 Reyting doskasi")])
    return card("👤 SHAXSIY KABINET", "Natijalaringiz va yutuqlaringiz", body), kb(rows)


def send_profile(message):
    html, markup = profile_view(message.from_user)
    send_html(bot, message.chat.id, html, reply_markup=markup)


def send_rank(message):
    """Reyting: veb-ilova tugmasi + bot ichidagi TOP-10."""
    db = get_db()
    rows = db.leaderboard("week", 10)
    if not rows:
        body = "Hozircha natijalar yo'q. Birinchi bo'lib test ishlang — doskaning boshida siz bo'lasiz! 🚀"
    else:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for i, r in enumerate(rows, 1):
            total = int(r["total"] or 0)
            pct = round(100 * int(r["correct"] or 0) / total) if total else 0
            lines.append(f"{medals.get(i, f'<b>{i}.</b>')} {esc(r['name'] or 'Ishtirokchi')} — "
                         f"<b>{int(r['correct'] or 0)}</b> to'g'ri · {pct}%")
        body = "\n".join(lines)
    markup = kb([[rank_btn("🏆 To'liq reyting (Mini-App)")], [("📅 Oylik TOP", "rank:month"), ("🌍 Hamma vaqt", "rank:all")]])
    send_html(bot, message.chat.id, card("🏆 HAFTALIK TOP-10", "To'g'ri javoblar soni bo'yicha", body), reply_markup=markup)


@on_cb("rank:")
def cb_rank(call):
    period = call.data.split(":")[1]
    answer_cb(call)
    if period == "top":
        period = "week"
    labels = {"week": "HAFTALIK", "month": "OYLIK", "all": "UMUMIY"}
    rows = get_db().leaderboard(period, 10)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for i, r in enumerate(rows, 1):
        total = int(r["total"] or 0)
        pct = round(100 * int(r["correct"] or 0) / total) if total else 0
        lines.append(f"{medals.get(i, f'<b>{i}.</b>')} {esc(r['name'] or 'Ishtirokchi')} — "
                     f"<b>{int(r['correct'] or 0)}</b> to'g'ri · {pct}%")
    body = "\n".join(lines) or "Hozircha natijalar yo'q."
    others = [p for p in ("week", "month", "all") if p != period]
    names = {"week": "📅 Haftalik", "month": "📅 Oylik", "all": "🌍 Hamma vaqt"}
    markup = kb([[(names[p], f"rank:{p}") for p in others], [rank_btn("🏆 Mini-App")]])
    show(call, card(f"🏆 {labels[period]} TOP-10", "To'g'ri javoblar soni bo'yicha", body), markup)


@on_cb("prof:badges")
def cb_badges(call):
    answer_cb(call)
    have = set(get_db().get_badges(call.from_user.id))
    lines = []
    for code, (icon, title, desc) in levels.BADGES.items():
        if code in have:
            lines.append(f"{icon} <b>{title}</b> — {desc} ✅")
        else:
            lines.append(f"🔒 <b>{title}</b> — <i>{desc}</i>")
    show(call, card("🏅 NISHONLAR", f"{len(have)}/{len(levels.BADGES)} ochilgan", "\n".join(lines)),
         kb([[("🔙 Kabinet", "prof:back")]]))


@on_cb("prof:back")
def cb_prof_back(call):
    answer_cb(call)
    html, markup = profile_view(call.from_user)
    show(call, html, markup)


@on_cb("prof:invite")
def cb_invite(call):
    answer_cb(call)
    link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{call.from_user.id}"
    body = (f"Do'stingizni taklif qiling — u botga kirganida <b>sizga +30 XP</b>, unga ham <b>+30 XP</b> beriladi.\n\n"
            f"🔗 Sizning havolangiz:\n<code>{link}</code>")
    show(call, card("🤝 DO'ST TAKLIF QILISH", "", body),
         kb([[("📤 Do'stga yuborish", f"https://t.me/share/url?url={link}&text=Ona tili va adabiyotga tayyorlanish uchun AI yordamchi", "url")],
             [("🔙 Kabinet", "prof:back")]]))

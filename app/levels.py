"""Daraja (unvon) va nishonlar tizimi."""
from app.textfmt import bar

# (minimal XP, nom, belgi)
LEVELS = [
    (0, "Boshlovchi", "🌱"),
    (100, "Savodxon", "📘"),
    (300, "Munshiy", "✒️"),
    (700, "Fozil", "🎓"),
    (1500, "Adib", "🏅"),
    (3000, "Alloma", "👑"),
]

BADGES = {
    "first_test": ("🎯", "Birinchi qadam", "Birinchi testni yakunladingiz"),
    "streak_3": ("🔥", "Uch kunlik seriya", "3 kun ketma-ket kirdingiz"),
    "streak_7": ("⚡", "Haftalik seriya", "7 kun ketma-ket kirdingiz"),
    "streak_30": ("🌟", "Oylik seriya", "30 kun ketma-ket kirdingiz"),
    "perfect": ("💯", "Benuqson", "Kamida 5 savolli testda 100% natija"),
    "marathon": ("🏃", "Marafonchi", "Jami 100 ta savolga javob berdingiz"),
    "mistake_fixer": ("🛠", "Xato tuzatuvchi", "Xatolar ustida ishlab, 10 ta xatoni tuzatdingiz"),
    "essay_pro": ("✍️", "Esse ustasi", "3 ta esseni tekshirtirdingiz"),
    "inviter": ("🤝", "Elchi", "Do'stingizni botga taklif qildingiz"),
    "daily_7": ("📅", "Kun savoli ixlosmandi", "7 ta kun savoliga javob berdingiz"),
}


def level_for(points):
    cur = LEVELS[0]
    nxt = None
    for i, lv in enumerate(LEVELS):
        if points >= lv[0]:
            cur = lv
            nxt = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    return cur, nxt


def level_line(points):
    cur, nxt = level_for(points)
    if not nxt:
        return f"{cur[2]} <b>{cur[1]}</b> · eng yuqori daraja!"
    span = nxt[0] - cur[0]
    got = points - cur[0]
    return (
        f"{cur[2]} <b>{cur[1]}</b>  {bar(got, span)}  {points}/{nxt[0]} XP\n"
        f"<i>Keyingi daraja: {nxt[2]} {nxt[1]}</i>"
    )


def badge_title(code):
    b = BADGES.get(code)
    return f"{b[0]} {b[1]}" if b else code

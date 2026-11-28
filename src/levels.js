import { bar } from "./textfmt.js";

export const LEVELS = [
  [0, "Boshlovchi", "🌱"],
  [100, "Savodxon", "📘"],
  [300, "Munshiy", "✒️"],
  [700, "Fozil", "🎓"],
  [1500, "Adib", "🏅"],
  [3000, "Alloma", "👑"],
];

export const BADGES = {
  first_test: ["🎯", "Birinchi qadam", "Birinchi testni yakunladingiz"],
  streak_3: ["🔥", "Uch kunlik seriya", "3 kun ketma-ket kirdingiz"],
  streak_7: ["⚡", "Haftalik seriya", "7 kun ketma-ket kirdingiz"],
  streak_30: ["🌟", "Oylik seriya", "30 kun ketma-ket kirdingiz"],
  perfect: ["💯", "Benuqson", "Kamida 5 savolli testda 100% natija"],
  marathon: ["🏃", "Marafonchi", "Jami 100 ta savolga javob berdingiz"],
  mistake_fixer: ["🛠", "Xato tuzatuvchi", "Xatolar ustida ishlab, 10 ta xatoni tuzatdingiz"],
  essay_pro: ["✍️", "Esse ustasi", "3 ta esseni tekshirtirdingiz"],
  inviter: ["🤝", "Elchi", "Do'stingizni botga taklif qildingiz"],
  weekly_winner: ["🏆", "Hafta g'olibi", "Haftalik TOP-3 ga kirdingiz"],
  duelist: ["⚔️", "Bellashuvchi", "Do'st bilan bellashuvda g'alaba qozondingiz"],
  daily_7: ["📅", "Kun savoli ixlosmandi", "7 ta kun savoliga javob berdingiz"],
};

export function levelFor(points) {
  let cur = LEVELS[0];
  let nxt = null;
  for (let i = 0; i < LEVELS.length; i++) {
    if (points >= LEVELS[i][0]) {
      cur = LEVELS[i];
      nxt = i + 1 < LEVELS.length ? LEVELS[i + 1] : null;
    }
  }
  return [cur, nxt];
}

export function levelLine(points) {
  const [cur, nxt] = levelFor(points);
  if (!nxt) return `${cur[2]} <b>${cur[1]}</b> · eng yuqori daraja!`;
  const span = nxt[0] - cur[0];
  const got = points - cur[0];
  return `${cur[2]} <b>${cur[1]}</b>  ${bar(got, span)}  ${points}/${nxt[0]} XP\n<i>Keyingi daraja: ${nxt[2]} ${nxt[1]}</i>`;
}

export function badgeTitle(code) {
  const b = BADGES[code];
  return b ? `${b[0]} ${b[1]}` : code;
}

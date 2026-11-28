import { MODES } from "./translit.js";

export const BTN_QUIZ = "🎯 Test yechish";
export const BTN_CERT = "🎓 Milliy sertifikat";
export const BTN_DAILY = "📅 Kun savoli";
export const BTN_MISTAKES = "🔁 Xatolar ustida";
export const BTN_ESSAY = "✍️ Esse tekshirish";
export const BTN_RESEARCH = "📚 Ilmiy tadqiqot";
export const BTN_TRANSLIT = "🔤 Alifbo o'girish";
export const BTN_TOOLS = "🛠 Til vositalari";
export const BTN_RATING = "🏆 Reyting";
export const BTN_PROFILE = "👤 Profil va sinf";

export const MENU_BUTTONS = new Set([
  BTN_QUIZ, BTN_CERT, BTN_DAILY, BTN_MISTAKES, BTN_ESSAY,
  BTN_RESEARCH, BTN_TRANSLIT, BTN_TOOLS, BTN_RATING, BTN_PROFILE,
]);

export const btn = (text, callback_data) => ({ text, callback_data });
export const urlBtn = (text, url) => ({ text, url });

export function mainMenu() {
  return {
    keyboard: [
      [{ text: BTN_QUIZ }, { text: BTN_CERT }],
      [{ text: BTN_DAILY }, { text: BTN_MISTAKES }],
      [{ text: BTN_ESSAY }, { text: BTN_RESEARCH }],
      [{ text: BTN_TRANSLIT }, { text: BTN_TOOLS }],
      [{ text: BTN_RATING }, { text: BTN_PROFILE }],
    ],
    resize_keyboard: true,
    input_field_placeholder: "Bo'limni tanlang yoki matn yuboring...",
  };
}

export function subscribeKb(channelUrl) {
  return {
    inline_keyboard: [
      [urlBtn("📢 Kanalga a'zo bo'lish", channelUrl)],
      [btn("✅ Tekshirish", "check_sub")],
    ],
  };
}

export function quizMenu() {
  return {
    inline_keyboard: [
      [btn("🎲 Tezkor test (10 savol)", "q_quick")],
      [btn("📚 Bo'lim bo'yicha (Baza)", "q_sections"), btn("🤖 AI mavzu bo'yicha", "q_ai_topic")],
      [btn("📄 Matn asosida test (AI)", "q_ai_text"), btn("⚔️ Do'st bilan bellashuv", "q_duel")],
      [btn("⏱ Imtihon rejimi (25 savol · 20 daq)", "q_exam"), btn("👥 Guruhda viktorina", "q_group_help")],
    ],
  };
}

export function sectionsKb(sections, counts) {
  const rows = [];
  for (let i = 0; i < sections.length; i += 2) {
    const row = sections.slice(i, i + 2).map((s, idx) =>
      btn(`${s} (${counts[s] || 0})`, `q_sec:${i + idx}`)
    );
    rows.push(row);
  }
  rows.push([btn("🔙 Orqaga", "q_back")]);
  return { inline_keyboard: rows };
}

export function countKb(prefix) {
  return {
    inline_keyboard: [
      [5, 10, 15, 20].map(n => btn(`${n} ta`, `${prefix}:${n}`)),
      [btn("🔙 Orqaga", "q_back")],
    ],
  };
}

export function quizControl(mode, idx, total) {
  const row = [btn("💡 Tushuntirish", `q_hint:${mode}:${idx}`)];
  if (idx + 1 < total) row.push(btn("⏭ O'tkazib yuborish", `q_skip:${mode}:${idx}`));
  row.push(btn("⏹ Yakunlash", `q_stop:${mode}`));
  return { inline_keyboard: [row] };
}

export function quizResultKb(retryCb, hasMistakes = false) {
  const rows = [[btn("🔄 Qayta ishlash", retryCb)]];
  if (hasMistakes) rows[0].push(btn("🔁 Xatolarni ishlash", "mistakes_start"));
  rows.push([btn("🎯 Test menyusi", "q_back"), btn("🏆 Reyting", "rating:all")]);
  return { inline_keyboard: rows };
}

export function certMenu() {
  return {
    inline_keyboard: [
      [btn("📋 Full Mock (25 savol · 30 daq)", "cert:full")],
      [btn("📖 O'qish savodxonligi (AI)", "cert:reading"), btn("📐 Til me'yorlari (Baza)", "cert:norms")],
      [btn("🏛 Adabiyot (5-11-sinf)", "cert:lit"), btn("✍️ Esse (24 ballik mezon)", "cert:essay")],
    ],
  };
}

export function essayMenu() {
  return {
    inline_keyboard: [
      [btn("✍️ Esse yuborish (matn yoki rasm)", "essay:send")],
      [btn("🎲 Mavzu generatsiya", "essay:topic"), btn("📖 Namuna esselar (5 ta)", "essay:samples")],
      [btn("📋 24 ballik mezonlar", "essay:rubric")],
    ],
  };
}

export function essaySamplesKb(samples) {
  const rows = samples.map((s, i) => [btn(`${i + 1}. ${s.title.slice(0, 38)}`, `essay:sample:${i}`)]);
  rows.push([btn("🔙 Orqaga", "essay:back")]);
  return { inline_keyboard: rows };
}

export function researchMenu() {
  return {
    inline_keyboard: [
      [btn("🔬 Ilmiy tahlil", "res:analyze"), btn("📝 Annotatsiya (UZ/RU/EN)", "res:abstract")],
      [btn("📖 OAK / GOST adabiyotlar", "res:refs"), btn("🔄 Parafraz va akademik uslub", "res:paraphrase")],
      [btn("🗂 Dissertatsiya rejasi", "res:outline"), btn("🔑 Kalit so'zlar + UDK", "res:keywords")],
    ],
  };
}

export function translitMenu(active = "lat2new") {
  const rows = [];
  for (const [key, [label]] of Object.entries(MODES)) {
    const mark = key === active ? "✅ " : "";
    rows.push([btn(`${mark}${label}`, `tr_mode:${key}`)]);
  }
  rows.push([btn("✨ Avtomatik aniqlash", "tr_auto")]);
  return { inline_keyboard: rows };
}

export function toolsMenu() {
  return {
    inline_keyboard: [
      [btn("✅ Imlo va uslub tuzatish", "tool:spell"), btn("📚 So'z izohi (sinonim/etimologiya)", "tool:define")],
      [btn("🧩 Morfologik tahlil", "tool:morph"), btn("🔗 Sintaktik tahlil", "tool:syntax")],
      [btn("📜 G'azal / she'r tahlili (aruz)", "tool:poem"), btn("💬 Maqol va ibora izohi", "tool:idiom")],
    ],
  };
}

export function ratingTabs(active = "all") {
  const tabs = [
    ["all", "Umumiy"],
    ["week", "Haftalik"],
    ["month", "Oylik"],
    ["points", "Ballar"],
  ];
  return {
    inline_keyboard: [
      tabs.map(([k, title]) => btn(k === active ? `• ${title} •` : title, `rating:${k}`)),
    ],
  };
}

export function profileKb(reminders, quizAlerts = true) {
  const rTxt = reminders ? "🔔 Eslatma: Yoqilgan" : "🔕 Eslatma: O'chirilgan";
  const qTxt = quizAlerts ? "📢 Viktorina: Yoqilgan" : "🔕 Viktorina: O'chirilgan";
  return {
    inline_keyboard: [
      [btn("🏅 Yutuqlar (Badges)", "prof:badges"), btn("📅 Imtihon sanasi", "prof:exam")],
      [btn("🤝 Do'st taklif qilish", "prof:invite"), btn("🏫 Sinf / guruh", "prof:class")],
      [btn(rTxt, "prof:rem_toggle"), btn(qTxt, "prof:qalert_toggle")],
      [btn("📜 Sertifikat (SVG)", "prof:cert")],
    ],
  };
}

export function classMenu(isTeacher = false) {
  const rows = [
    [btn("➕ Yangi sinf ochish (O'qituvchi)", "cls:create")],
    [btn("🔑 Kod bilan qo'shilish (O'quvchi)", "cls:join")],
  ];
  if (isTeacher) rows.push([btn("📋 Mening sinflarim", "cls:my")]);
  rows.push([btn("🎓 A'zo sinflarim", "cls:joined")]);
  return { inline_keyboard: rows };
}

export function adminMenu() {
  return {
    inline_keyboard: [
      [btn("📊 Statistika", "adm:stats"), btn("👥 Foydalanuvchilar", "adm:users:0")],
      [btn("📢 Hammaga xabar", "adm:broadcast"), btn("📣 Kanalga post", "adm:ch_post")],
      [btn("📝 Kanalga test", "adm:ch_test"), btn("🏆 Kanalga reyting", "adm:ch_board")],
      [btn("📥 CSV eksport", "adm:export"), btn("💚 Tizim holati", "adm:health")],
    ],
  };
}

export function adminUsersNav(page, totalPages) {
  const nav = [];
  if (page > 0) nav.push(btn("⬅️ Oldingi", `adm:users:${page - 1}`));
  if (page + 1 < totalPages) nav.push(btn("Keyingi ➡️", `adm:users:${page + 1}`));
  const rows = [];
  if (nav.length) rows.push(nav);
  rows.push([btn("🔙 Admin panel", "adm:menu")]);
  return { inline_keyboard: rows };
}

export function confirmKb(yesCb, noCb = "cancel") {
  return {
    inline_keyboard: [[btn("✅ Tasdiqlash", yesCb), btn("❌ Bekor qilish", noCb)]],
  };
}

export function groupLobbyKb(lobbyId, minPlayers = 2, count = 0) {
  return {
    inline_keyboard: [
      [btn(`➕ Qo'shilish (${count}/${minPlayers}+)`, `gq_join:${lobbyId}`)],
      [btn("🚀 Boshlash", `gq_start:${lobbyId}`), btn("❌ Bekor qilish", `gq_cancel:${lobbyId}`)],
    ],
  };
}

export function groupQuizControl(lobbyId) {
  return {
    inline_keyboard: [
      [btn("⏸ Pauza", `gq_pause:${lobbyId}`), btn("⏹ Tugatish", `gq_stop:${lobbyId}`)],
    ],
  };
}

export function groupPausedKb(lobbyId) {
  return {
    inline_keyboard: [
      [btn("▶️ Davom ettirish", `gq_resume:${lobbyId}`), btn("⏹ Tugatish", `gq_stop:${lobbyId}`)],
    ],
  };
}

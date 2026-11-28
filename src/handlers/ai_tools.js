import ESSAYS from "../data/essays.json";
import { generateText, generateVision, AIError, OffTopic } from "../ai.js";
import { convert, detectMode, MODES } from "../translit.js";
import { esc, card, mdToHtml } from "../textfmt.js";
import {
  essayMenu, essaySamplesKb, researchMenu, translitMenu, toolsMenu, btn,
} from "../keyboards.js";

const ESSAY_RUBRIC_TEXT =
  "<b>📋 Milliy sertifikat esse baholash mezonlari (jami 24 ball):</b>\n\n" +
  "1. <b>Mavzuga muvofiqlik va mazmun (0–6 ball)</b> — tezisning aniqligi, dalillar asosliligi\n" +
  "2. <b>Tuzilish va mantiqiy izchillik (0–6 ball)</b> — kirish, asosiy qism (2–3 abzats), xulosa\n" +
  "3. <b>Leksik boylik va uslubiy aniqlik (0–6 ball)</b> — adabiy til me'yori, takrorlardan xolilik\n" +
  "4. <b>Imlo, punktuatsiya va grammatika (0–6 ball)</b> — rasmiy imlo qoidalariga rioya";

const ESSAY_SYSTEM_PROMPT =
  "Siz BMB (DTM) Milliy sertifikat esse tekshiruvchi bosh ekspertsiz. Quyidagi esseni 24 ballik mezon " +
  "(Mazmun 0-6, Tuzilish 0-6, Leksika/Uslub 0-6, Imlo/Punktuatsiya 0-6) bo'yicha batafsil baholang:\n" +
  "1) Har bir mezon bo'yicha aniq ball va izoh;\n" +
  "2) Jami ball (X / 24) va taxminiy daraja (A+, A, B+, B, C+, C);\n" +
  "3) Topilgan imloviy, punktuatsion va uslubiy xatolar ro'yxati (noto'g'ri → to'g'ri);\n" +
  "4) Kuchaytirish uchun 3 ta aniq tavsiya.";

export async function openEssayMenu(ctx, chatId, editMid = null) {
  const txt = card(
    "✍️ Esse tekshirish va tayyorgarlik",
    "BMB 24 ballik mezon · matn va qo'lyozma rasm tahlili",
    "• <b>Esse yuborish</b> — matn yozing yoki daftar/qog'oz rasmini yuboring\n" +
    "• <b>Mavzu generatsiya</b> — imtihon darajasidagi yangi mavzular\n" +
    "• <b>Namuna esselar</b> — yuqori balli tayyor namunalar"
  );
  if (editMid) await ctx.tg.editHtml(chatId, editMid, txt, essayMenu());
  else await ctx.tg.sendHtml(chatId, txt, essayMenu());
}

export async function handleEssayCallback(ctx, cq, data) {
  const uid = cq.from.id;
  const chatId = cq.message.chat.id;
  const mid = cq.message.message_id;
  const parts = data.split(":");
  const sub = parts[1];

  if (sub === "back") {
    await openEssayMenu(ctx, chatId, mid);
    return true;
  }
  if (sub === "rubric") {
    await ctx.tg.editHtml(chatId, mid, ESSAY_RUBRIC_TEXT, essayMenu());
    return true;
  }
  if (sub === "send") {
    await ctx.db.setState(uid, "await_essay", {});
    await ctx.tg.sendHtml(
      chatId,
      "✍️ <b>Esseni yuboring</b> (kamida 80 so'zli matn yoki qo'lyozma rasmi).\n" +
      "<i>Istasangiz birinchi qatorda esse mavzusini ham yozing.</i>"
    );
    return true;
  }
  if (sub === "topic") {
    if (!await ctx.checkAiGuard(uid, chatId, "esse mavzusi")) return true;
    const w = await ctx.tg.sendHtml(chatId, "⏳ Yangi esse mavzulari tuzilmoqda...");
    try {
      const res = await generateText(
        ctx.cfg,
        "O'zbek tili va adabiyotidan Milliy sertifikat darajasida 5 ta dolzarb muhokama (argumentativ) esse mavzusi " +
        "va har biri uchun qisqa tezis yo'nalishini bering.",
        0.7
      );
      await ctx.tg.deleteMessage(chatId, w.message_id);
      await ctx.tg.sendLong(chatId, res, essayMenu());
    } catch (e) {
      await ctx.tg.editHtml(chatId, w.message_id, `⚠️ ${esc(e.message)}`);
    }
    return true;
  }
  if (sub === "samples") {
    await ctx.tg.editHtml(chatId, mid, "📖 <b>Namuna esselardan birini tanlang:</b>", essaySamplesKb(ESSAYS));
    return true;
  }
  if (sub === "sample") {
    const item = ESSAYS[Number(parts[2])];
    if (!item) return true;
    const body = `<b>${esc(item.title)}</b>\n<i>Mezon balli: ${esc(item.score || "23/24")}</i>\n\n${esc(item.text)}`;
    await ctx.tg.sendLong(chatId, body, essaySamplesKb(ESSAYS), true);
    return true;
  }
  return false;
}

export async function runEssayReview(ctx, chatId, uid, text, photoFileId = null) {
  if (!await ctx.checkAiGuard(uid, chatId, text || "esse")) return;
  const w = await ctx.tg.sendHtml(chatId, "🔍 Esse 24 ballik mezon bo'yicha tahlil qilinmoqda...");
  try {
    let ans;
    if (photoFileId) {
      const { base64, mime } = await ctx.tg.downloadFile(photoFileId);
      const p = `${ESSAY_SYSTEM_PROMPT}\n\nRasmdagi qo'lyozma esseni avval o'qing, so'ng baholang.` +
        (text ? `\nMavzu/izoh: ${text}` : "");
      ans = await generateVision(ctx.cfg, p, base64, mime, 0.25);
    } else {
      ans = await generateText(ctx.cfg, `${ESSAY_SYSTEM_PROMPT}\n\nESSE MATNI:\n"""\n${text.slice(0, 6000)}\n"""`, 0.25);
    }
    await ctx.tg.deleteMessage(chatId, w.message_id);
    const cnt = await ctx.db.kvIncr(`essay_cnt:${uid}`, 1);
    await ctx.db.addPoints(uid, 20);
    if (cnt >= 3 && await ctx.db.awardBadge(uid, "essay_pro")) {
      await ctx.tg.sendHtml(chatId, "🏅 Yangi yutuq: <b>✍️ Esse ustasi</b>!");
    }
    await ctx.tg.sendLong(chatId, ans + "\n\n✨ *+20 XP qo'shildi!*");
  } catch (e) {
    await ctx.tg.editHtml(chatId, w.message_id, e instanceof OffTopic ? "⚠️ Faqat o'zbek tilidagi esselar tekshiriladi." : `⚠️ ${esc(e.message)}`);
  }
}

const RES_PROMPTS = {
  analyze: ["🔬 Ilmiy tahlil", "Maqola mavzusi yoki matnini yuboring — lingvistik/adabiy ilmiy tahlil beraman:",
    "Quyidagi filologik mavzu/matnni akademik nuqtayi nazardan tahlil qiling (dolzarbligi, nazariy asoslar, metodlar, ilmiy xulosalar):"],
  abstract: ["📝 Annotatsiya (UZ / RU / EN)", "Maqola sarlavhasi va asosiy mazmunini yuboring:",
    "Quyidagi ilmiy maqola uchun akademik uslubda 3 tilda (O'zbek, Rus, Ingliz) 100-130 so'zli annotatsiya va 5 tadan kalit so'z yozing:"],
  refs: ["📖 OAK / GOST adabiyotlar", "Tadqiqot mavzusini yuboring — OAK va GOST 7.1 talabiga mos adabiyotlar ro'yxatini tuzaman:",
    "Quyidagi filologik mavzu bo'yicha O'zbekiston OAK va GOST standartiga mos haqiqiy ilmiy manbalar ro'yxatini tuzing (to'qima manba yozmang!):"],
  paraphrase: ["🔄 Akademik parafraz", "Matnni yuboring — ilmiy uslubda qayta ishlab, plagiat xavfini kamaytiraman:",
    "Quyidagi matnni mazmunini saqlagan holda yuqori akademik o'zbek ilmiy uslubida parafraz qiling:"],
  outline: ["🗂 Dissertatsiya / BMI rejasi", "Tadqiqot mavzusini yuboring — boblar va paragraflar rejasini tuzaman:",
    "Quyidagi filologik mavzu bo'yicha PhD dissertatsiya yoki magistrlik ishi uchun 3 bobli batafsil reja, maqsad, vazifalar va obyekt-predmetni yozing:"],
  keywords: ["🔑 Kalit so'zlar + UDK", "Maqola mavzusi yoki annotatsiyasini yuboring:",
    "Quyidagi filologik maqola uchun 8-10 ta ilmiy kalit so'z (UZ/RU/EN) va mos UDK (Universal o'nlik tasnif) indeksini tavsiya eting:"],
};

export async function openResearchMenu(ctx, chatId, editMid = null) {
  const txt = card(
    "📚 Ilmiy tadqiqot yordamchisi",
    "OAK · GOST · Dissertatsiya va ilmiy maqolalar",
    "Filolog tadqiqotchilar, magistrant va doktorantlar uchun akademik vositalar:"
  );
  if (editMid) await ctx.tg.editHtml(chatId, editMid, txt, researchMenu());
  else await ctx.tg.sendHtml(chatId, txt, researchMenu());
}

export async function handleResearchCallback(ctx, cq, data) {
  const uid = cq.from.id;
  const chatId = cq.message.chat.id;
  const kind = data.split(":")[1];
  const cfg = RES_PROMPTS[kind];
  if (!cfg) return false;
  await ctx.db.setState(uid, "await_research", { kind });
  await ctx.tg.sendHtml(chatId, `<b>${cfg[0]}</b>\n\n${cfg[1]}`);
  return true;
}

export async function runResearch(ctx, chatId, uid, kind, text) {
  const cfg = RES_PROMPTS[kind] || RES_PROMPTS.analyze;
  if (!await ctx.checkAiGuard(uid, chatId, text)) return;
  const w = await ctx.tg.sendHtml(chatId, "⏳ Akademik tahlil tayyorlanmoqda...");
  try {
    const ans = await generateText(ctx.cfg, `${cfg[2]}\n\n"""\n${text.slice(0, 5000)}\n"""`, 0.3);
    await ctx.tg.deleteMessage(chatId, w.message_id);
    await ctx.tg.sendLong(chatId, ans, researchMenu());
  } catch (e) {
    await ctx.tg.editHtml(chatId, w.message_id, e instanceof OffTopic ? "⚠️ Faqat filologik ilmiy mavzular." : `⚠️ ${esc(e.message)}`);
  }
}

export async function openTranslitMenu(ctx, chatId, uid, editMid = null) {
  const mode = (await ctx.db.kvGet(`tr_mode:${uid}`, "lat2new")) || "lat2new";
  const txt = card(
    "🔤 Alifbo o'girish (Transliteratsiya)",
    `Faol yo'nalish: ${MODES[mode]?.[0] || ""}`,
    "Yo'nalishni tanlang va istalgan uzunlikdagi matnni yuboring — soniyada o'girib beraman!\n\n" +
    "<i>Qo'llab-quvvatlanadi: Lotin ↔ Yangi alifbo (Ö Ğ Ş Ç), Kirill ↔ Lotin.</i>"
  );
  if (editMid) await ctx.tg.editHtml(chatId, editMid, txt, translitMenu(mode));
  else await ctx.tg.sendHtml(chatId, txt, translitMenu(mode));
}

export async function handleTranslitCallback(ctx, cq, data) {
  const uid = cq.from.id;
  const chatId = cq.message.chat.id;
  const mid = cq.message.message_id;
  if (data === "tr_auto") {
    await ctx.db.setState(uid, "await_translit", { mode: "auto" });
    await ctx.tg.sendHtml(chatId, "✨ <b>Matn yuboring</b> — alifboni avtomatik aniqlab o'giraman:");
    return true;
  }
  if (data.startsWith("tr_mode:")) {
    const mode = data.split(":")[1];
    await ctx.db.kvSet(`tr_mode:${uid}`, mode);
    await ctx.db.setState(uid, "await_translit", { mode });
    await openTranslitMenu(ctx, chatId, uid, mid);
    await ctx.tg.sendHtml(chatId, `✏️ <b>${esc(MODES[mode][0])}</b> — matnni yuboring:`);
    return true;
  }
  return false;
}

export async function runTranslit(ctx, chatId, uid, text, forceMode = null) {
  const saved = (await ctx.db.kvGet(`tr_mode:${uid}`, "lat2new")) || "lat2new";
  const mode = (!forceMode || forceMode === "auto") ? detectMode(text) : forceMode;
  const res = convert(mode, text);
  const label = MODES[mode]?.[0] || mode;
  await ctx.tg.sendLong(
    chatId,
    `<b>🔤 ${esc(label)}:</b>\n\n<code>${esc(res)}</code>`,
    translitMenu(saved),
    true
  );
}

const TOOL_PROMPTS = {
  spell: ["✅ Imlo va uslub tuzatish", "Matnni yuboring — xatolarni topib, to'g'rilangan matnni beraman:",
    "Quyidagi o'zbekcha matnning imloviy, punktuatsion va uslubiy xatolarini tuzating. " +
    "Avval to'g'rilangan to'liq matnni, so'ng har bir tuzatishning qisqa qoidasini yozing:"],
  define: ["📚 So'z izohi", "So'z yoki iborani yuboring:",
    "Quyidagi o'zbekcha so'zning to'liq izohli lug'at ma'nolarini, sinonimlarini, antonimini, etimologiyasini va 2 ta gapda qo'llanishini bering:"],
  morph: ["🧩 Morfologik tahlil", "Gap yoki so'zlar yuboring:",
    "Quyidagi matndagi so'zlarni so'z turkumlari, tuzilishi (sodda/qo'shma/juft) va qo'shimchalar (so'z yasovchi, shakl yasovchi) bo'yicha to'liq morfologik tahlil qiling:"],
  syntax: ["🔗 Sintaktik tahlil", "Gap yuboring — gap bo'laklari va turi bo'yicha tahlil qilaman:",
    "Quyidagi gapni to'liq sintaktik tahlil qiling: gapning turi (tuzilishi va ifoda maqsadiga ko'ra), ega, kesim, to'ldiruvchi, aniqlovchi, hol va so'z birikmalari:"],
  poem: ["📜 G'azal / she'r tahlili", "She'r yoki bayt yuboring:",
    "Quyidagi she'r/g'azalni badiiy-poetik tahlil qiling: mavzu, g'oya, vazni (aruz bahri yoki barmoq), qofiya, radif va badiiy san'atlar (tashbeh, istiora, tajnis, talmeh va h.k.):"],
  idiom: ["💬 Maqol va ibora izohi", "Maqol yoki frazeologik iborani yuboring:",
    "Quyidagi o'zbek xalq maqoli yoki frazeologik iborasining kelib chiqishi, ko'chma ma'nosi, ma'nodoshlari va nutqda qo'llanishini izohlang:"],
};

export async function openToolsMenu(ctx, chatId, editMid = null) {
  const txt = card(
    "🛠 Til va tahlil vositalari",
    "Imlo · Morfologiya · Sintaksis · Aruz · Lug'at",
    "Kerakli tahlil turini tanlang:"
  );
  if (editMid) await ctx.tg.editHtml(chatId, editMid, txt, toolsMenu());
  else await ctx.tg.sendHtml(chatId, txt, toolsMenu());
}

export async function handleToolCallback(ctx, cq, data) {
  const uid = cq.from.id;
  const chatId = cq.message.chat.id;
  const kind = data.split(":")[1];
  const cfg = TOOL_PROMPTS[kind];
  if (!cfg) return false;
  await ctx.db.setState(uid, "await_tool", { kind });
  await ctx.tg.sendHtml(chatId, `<b>${cfg[0]}</b>\n\n${cfg[1]}`);
  return true;
}

export async function runTool(ctx, chatId, uid, kind, text) {
  const cfg = TOOL_PROMPTS[kind] || TOOL_PROMPTS.spell;
  if (!await ctx.checkAiGuard(uid, chatId, text)) return;
  const w = await ctx.tg.sendHtml(chatId, "⏳ Tahlil qilinmoqda...");
  try {
    const ans = await generateText(ctx.cfg, `${cfg[2]}\n\n"""\n${text.slice(0, 4000)}\n"""`, 0.25);
    await ctx.tg.deleteMessage(chatId, w.message_id);
    await ctx.tg.sendLong(chatId, ans, toolsMenu());
  } catch (e) {
    await ctx.tg.editHtml(chatId, w.message_id, e instanceof OffTopic ? "⚠️ Faqat til va adabiyot so'rovlari." : `⚠️ ${esc(e.message)}`);
  }
}

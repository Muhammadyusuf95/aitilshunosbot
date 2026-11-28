import { checkHardViolation } from "./security.js";

export const SYSTEM_INSTRUCTION =
  "Siz O'zbekiston Respublikasi Fanlar akademiyasi Til va adabiyot instituti yetakchi filologi, " +
  "OAK eksperti hamda BMB (DTM) va Milliy sertifikat bo'yicha bosh ilmiy-metodistsiz.\n\n" +
  "UMUMIY QOIDALAR:\n" +
  "1. Barcha javoblar o'zbek tilida (lotin yozuvi), amaldagi rasmiy imlo va orfoepiyaga mos bo'lsin.\n" +
  "2. Aniq bilmagan ma'lumotni to'qimang. Ishonchingiz komil bo'lmasa, buni ochiq ayting.\n" +
  "3. Muallif, asar, iqtibos va manbalarni faqat haqiqiy bo'lganda keltiring; sun'iy manba yozmang.\n\n" +
  "TEST SAVOLLARI UCHUN:\n" +
  "1. Savol, variantlar va izohlar akademik aniqlikda, imloviy-grammatik xatosiz bo'lsin.\n" +
  "2. Har bir savolda aynan 4 ta turli variant va bitta mutlaqo to'g'ri javob bo'lsin; " +
  "'correct_option_id' to'g'ri variantning 0..3 indeksi bo'lsin.\n" +
  "3. Adabiyot savollari amaldagi 5-11-sinf darsliklariga mos bo'lsin.\n\n" +
  "FAOLIYAT DOIRASI (QAT'IY): faqat tilshunoslik, ona tili, adabiyot, filologik ilmiy tadqiqot va shu fanlarni " +
  "o'qitish metodikasi.\n" +
  "QUYIDAGILAR TAQIQLANGAN: diniy mavzular; siyosat; ekstremizm; davlat, davlat rahbari va amaldorlarni maqtash yoki " +
  "tanqid qilish; davlat tuzumi va qonunchilikni muhokama qilish; turli oqim va firqalarga oid mavzular; shaxsni " +
  "kamsituvchi, haqoratlovchi, qadr-qimmatini toptovchi mazmun; behayo va nomaqbul kontent; tibbiyot, huquq, moliya, " +
  "texnologiya va boshqa sohalarga oid maslahat va ma'lumotlar.\n" +
  "Agar so'rov (yoki unga ilova qilingan matn/rasm) doiradan tashqari bo'lsa yoki taqiqlangan mavzuni o'z ichiga " +
  "olsa — hech qanday izoh yozmasdan FAQAT shu so'zni qaytaring: OFFTOPIC_REFUSED\n" +
  "Adabiy asarning o'zida uchragan tarixiy-badiiy tafsilotlar tahlili (masalan, mumtoz she'rning poetik tili) " +
  "til va adabiyot nuqtayi nazaridan, neytral va akademik tarzda izohlanishi mumkin.\n\n" +
  "FORMAT: Telegramda o'qishga qulay — qisqa sarlavhalar (##), **qalin** ajratmalar, '-' bilan ro'yxatlar. " +
  "Jadval va murakkab Markdown ishlatmang.";

export class AIError extends Error {}
export class OffTopic extends AIError {}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function tryModels(apiKey, models, parts, generationConfig, systemInstruction) {
  let lastErr = "";
  for (const model of models) {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
        const body = {
          system_instruction: { parts: [{ text: systemInstruction }] },
          contents: [{ role: "user", parts }],
          generationConfig,
        };
        const resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          const msg = data?.error?.message || `HTTP ${resp.status}`;
          lastErr = `${model}: ${msg}`;
          const low = lastErr.toLowerCase();
          if (resp.status === 429 || low.includes("resource_exhausted")) {
            await sleep(2000 + attempt * 2000);
            continue;
          }
          if (resp.status === 503 || resp.status === 500 || low.includes("unavailable") || low.includes("overloaded")) {
            await sleep(1500 + attempt * 1000);
            continue;
          }
          break;
        }
        const text = (data?.candidates?.[0]?.content?.parts || [])
          .map(p => p.text || "")
          .join("")
          .trim();
        if (text) return { text, err: "" };
        lastErr = `${model}: bo'sh javob`;
        break;
      } catch (e) {
        lastErr = `${model}: ${e.message || e}`;
        break;
      }
    }
  }
  return { text: null, err: lastErr };
}

async function discoverModels(apiKey) {
  try {
    const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(apiKey)}`);
    const data = await resp.json();
    return (data.models || [])
      .filter(m =>
        (m.name || "").includes("flash") &&
        (m.supportedGenerationMethods || []).includes("generateContent") &&
        !["image", "tts", "live", "audio", "thinking-exp"].some(x => m.name.includes(x))
      )
      .map(m => m.name.replace(/^models\//, ""))
      .sort()
      .reverse();
  } catch {
    return [];
  }
}

async function callGemini(cfg, parts, temperature, system = SYSTEM_INSTRUCTION, jsonMode = false) {
  if (!cfg.GEMINI_API_KEY) throw new AIError("GEMINI_API_KEY sozlanmagan.");
  const genCfg = { temperature };
  if (jsonMode) genCfg.responseMimeType = "application/json";

  let { text, err } = await tryModels(cfg.GEMINI_API_KEY, cfg.GEMINI_MODELS, parts, genCfg, system);
  if (!text && (err.includes("404") || err.toLowerCase().includes("not found") || err.toLowerCase().includes("not supported"))) {
    const extra = (await discoverModels(cfg.GEMINI_API_KEY)).filter(m => !cfg.GEMINI_MODELS.includes(m));
    if (extra.length) {
      const r2 = await tryModels(cfg.GEMINI_API_KEY, extra.slice(0, 4), parts, genCfg, system);
      text = r2.text;
      err = r2.err || err;
    }
  }
  if (!text) throw new AIError((err || "Noma'lum xatolik").slice(0, 400));
  if (text.slice(0, 80).includes("OFFTOPIC_REFUSED")) throw new OffTopic("OFFTOPIC_REFUSED");
  return text;
}

export async function generateText(cfg, prompt, temperature = 0.3, system = SYSTEM_INSTRUCTION) {
  return callGemini(cfg, [{ text: prompt }], temperature, system, false);
}

export async function generateVision(cfg, prompt, base64Data, mime = "image/jpeg", temperature = 0.2) {
  return callGemini(
    cfg,
    [{ inline_data: { mime_type: mime, data: base64Data } }, { text: prompt }],
    temperature,
    SYSTEM_INSTRUCTION,
    false
  );
}

function extractJson(raw) {
  let s = raw.trim();
  const fence = s.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fence) s = fence[1].trim();
  try {
    return JSON.parse(s);
  } catch {}
  for (const [o, c] of [["[", "]"], ["{", "}"]]) {
    const a = s.indexOf(o);
    const b = s.lastIndexOf(c);
    if (a !== -1 && b > a) {
      try {
        return JSON.parse(s.slice(a, b + 1));
      } catch {}
    }
  }
  throw new AIError("JSON o'qib bo'lmadi");
}

export async function generateJson(cfg, prompt, temperature = 0.4, system = SYSTEM_INSTRUCTION) {
  const raw = await callGemini(cfg, [{ text: prompt }], temperature, system, true);
  return extractJson(raw);
}

export function validateQuestion(q) {
  try {
    if (!q || typeof q !== "object") return null;
    const text = String(q.question || "").trim();
    const opts = Array.isArray(q.options) ? q.options.map(o => String(o).trim()) : [];
    const idx = Number(q.correct_option_id);
    if (!text || opts.length !== 4 || opts.some(o => !o)) return null;
    if (new Set(opts.map(o => o.toLowerCase())).size !== 4) return null;
    if (!Number.isInteger(idx) || idx < 0 || idx >= 4) return null;
    if (checkHardViolation(text + " " + opts.join(" "))) return null;
    return {
      question: text,
      options: opts,
      correct_option_id: idx,
      explanation: String(q.explanation || "").trim(),
      bolim: String(q.bolim || ""),
    };
  } catch {
    return null;
  }
}

const QUIZ_SCHEMA =
  'Faqat JSON massiv qaytaring, boshqa matn yozmang:\n' +
  '[{"question": "Savol matni", "options": ["A", "B", "C", "D"], ' +
  '"correct_option_id": 0, "explanation": "Qisqa ilmiy izoh (maks 180 belgi)"}]';

export async function generateQuiz(cfg, topicPrompt, count, seed = null, passage = null) {
  seed = seed || Math.floor(Date.now() / 1000) % 100000;
  let base =
    `${topicPrompt}\n\nTO'LIQ ${count} TA savol tuzing (seed #${seed}). Har bir savol — 4 variantli, ` +
    `bitta to'g'ri javobli, variantlar 90 belgidan oshmasin, savollar bir-birini takrorlamasin.\n`;
  if (passage) {
    base += `\nSavollar FAQAT quyidagi matn asosida bo'lsin:\n"""\n${passage.slice(0, 4000)}\n"""\n`;
  }
  let raw = await generateJson(cfg, base + QUIZ_SCHEMA, 0.5);
  if (raw && !Array.isArray(raw) && typeof raw === "object") {
    raw = raw.questions || raw.tests || Object.values(raw)[0];
  }
  const out = [];
  const seen = new Set();
  for (const q of Array.isArray(raw) ? raw : []) {
    const v = validateQuestion(q);
    if (v && !seen.has(v.question.toLowerCase())) {
      seen.add(v.question.toLowerCase());
      out.push(v);
    }
  }
  return out;
}

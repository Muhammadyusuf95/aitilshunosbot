import BAZA from "./data/baza.json";
import { validateQuestion } from "./ai.js";
import { tashkentDate } from "./config.js";

const RAW = Array.isArray(BAZA) ? BAZA : BAZA.questions || [];
const ALL = [];
const BY_SEC = {};

for (const q of RAW) {
  const v = validateQuestion(q);
  if (v) {
    v.bolim = q.bolim || "Umumiy";
    ALL.push(v);
    if (!BY_SEC[v.bolim]) BY_SEC[v.bolim] = [];
    BY_SEC[v.bolim].push(v);
  }
}

export const SECTIONS = Object.keys(BY_SEC).sort();

export function sectionCounts() {
  const out = {};
  for (const s of SECTIONS) out[s] = BY_SEC[s].length;
  return out;
}

export function totalCount() {
  return ALL.length;
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function sampleQuestions(section = null, count = 10) {
  const pool = section && BY_SEC[section] ? BY_SEC[section] : ALL;
  if (!pool.length) return [];
  return shuffle(pool).slice(0, Math.min(count, pool.length));
}

export function dailyQuestion(today = null) {
  if (!ALL.length) return null;
  today = today || tashkentDate();
  let h = 2166136261;
  for (let i = 0; i < today.length; i++) {
    h ^= today.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ALL[(h >>> 0) % ALL.length];
}

export function questionKey(q) {
  const s = (q.question || "").trim().toLowerCase();
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (let i = 0; i < s.length; i++) {
    const ch = s.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return ((h2 >>> 0).toString(16).padStart(8, "0") + (h1 >>> 0).toString(16).padStart(8, "0")).slice(0, 12);
}

import { cyrillicToLatin } from "./translit.js";

const APOS_RE = /[ʻʼ‘’`´′]/g;
const CYR_RE = /[а-яёўқғҳ]/i;

const PREFIX_POLITICS = [
  "prezident", "mirziyoyev", "karimov", "siyosat", "siyosiy", "saylov", "muxolifat", "deputat", "amaldor",
  "mansabdor", "hukumat", "hokimiyat", "hokimlik", "parlament", "senat", "oliy majlis", "vazirlar mahkamasi",
  "konstitutsiya", "qonunchilik", "davlat boshqaruvi", "davlat tuzumi", "tuzum", "rejim", "rahbariyat",
  "davlat rahbari", "mitingi", "miting", "norozilik", "namoyish", "inqilob", "to'ntarish", "korrupsiya",
  "poraxo'r", "partiya", "sanksiya",
];
const PREFIX_RELIGION = [
  "shariat", "masjid", "xristian", "cherkov", "yahudiy", "fatvo", "namoz", "ro'za", "islom", "qur'on", "alloh",
  "payg'ambar", "tafsir", "mazhab", "tariqat", "aqida", "bid'at", "salafiy", "bibliya", "injil", "tavrot",
  "ibodat", "vahiy", "diniy", "ateizm", "xalifalik", "takfir",
  "sekta", "missioner", "evangel", "buddizm", "hinduizm", "zardushtiy", "ibodatxona",
];
const PREFIX_EXTREMISM = [
  "ekstrem", "terror", "jihod", "vahobiy", "radikal", "mutaassib", "jangari", "separatist", "portlash",
  "portlat", "qotillik", "o'ldirish", "qurollan", "isis", "alqoida", "taliban", "hizbut", "hizb ut", "akromiy",
  "tashviqot", "bo'lginchi",
];
const PREFIX_INSULT = [
  "haqorat", "kamsit", "so'kin", "so'kish", "ahmoq", "tentak", "haromi", "kofir", "fosiq", "iflos", "la'nat",
  "pastkash", "yaramas", "qo'rqoq it", "mahmadana", "nodon odam", "tubanlik",
];
const PREFIX_OBSCENE = [
  "porno", "erotik", "jinsiy", "yalang'och", "yalangoch", "behayo", "fahsh", "fohisha", "intim", "seksual",
  "xxx", "nudes", "18+", "o'smir jinsiy", "qahba", "dalbayop", "siktir", "blya", "xuy", "pizd", "ebat",
];
const PREFIX_OTHER_FIELDS = [
  "tibbiyot", "davolash", "kasallik", "tashxis", "shifokor", "retsept", "prokuror", "advokat", "qamoq",
  "sudlanuvchi", "da'vogar", "jinoyat kodeksi", "kriptovalyuta", "bitkoin", "birja", "investitsiya",
  "fors-major", "soliq", "valyuta kursi", "gadjet narxi", "futbol", "bukmeker", "garov o'yin", "kazino",
  "dori-darmon", "narkotik", "giyohvand",
];
const STRICT = [
  "din", "sud", "dori", "modda", "oyat", "hadis", "imom", "mulla", "hizb", "hokim", "vazir", "qurol",
  "padar", "jalab", "taqvo", "xudo", "sik", "kot", "suka", "shayton", "gunoh", "savob",
  "milliy g'oya", "xalq dushmani",
];
const SUFFIX = "(?:lar|ni|ning|ga|da|dan|i|si|ini|ing|imiz|lik|ligi|iy|chi|ya|xona|ham|li|siz|ka|ga)*";
const GOV_CTX = [
  "davlat", "hukumat", "qonun", "rahbar", "tuzum", "mamlakat", "prezident", "vazir", "amaldor", "hokim",
  "o'zbekiston rahbar", "idora", "mansab",
];
const CRITIC_PRAISE = [
  "tanqid", "qoral", "ayblash", "ayblov", "zolim", "mustabid", "diktator", "noqonuniy", "adolatsiz",
  "yomon", "buzilgan", "kamchilik", "maqtov", "maqta", "ulug'la", "ulug'lash", "madh etish",
  "sharaflash", "ta'rifla", "tahsin", "e'tiroz", "isyon", "qarshi chiq", "ag'dar", "norozi",
  "zulm", "shafqatsiz", "firibgar", "o'g'ri",
];
const PHRASES = ["davlat boshqaruvi", "jinoyat kodeksi", "milliy g'oya"];

const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const wordsRe = (lst) => [...new Set(lst)].sort((a, b) => b.length - a.length).map(escRe).join("|");

const ALL_PREFIX = [
  ...PREFIX_POLITICS, ...PREFIX_RELIGION, ...PREFIX_EXTREMISM,
  ...PREFIX_INSULT, ...PREFIX_OBSCENE, ...PREFIX_OTHER_FIELDS,
];
const HARD_PREFIX = [...PREFIX_EXTREMISM, ...PREFIX_INSULT, ...PREFIX_OBSCENE];

const RE_PREFIX = new RegExp(`(?<![a-z])(?:${wordsRe(ALL_PREFIX)})`, "i");
const RE_HARD = new RegExp(`(?<![a-z])(?:${wordsRe(HARD_PREFIX)})`, "i");
const RE_STRICT = new RegExp(`(?<![a-z'])(?:${wordsRe(STRICT)})${SUFFIX}(?![a-z'])`, "i");
const RE_GOV = new RegExp(`(?<![a-z])(?:${wordsRe(GOV_CTX)})`, "i");
const RE_CRIT = new RegExp(`(?<![a-z])(?:${wordsRe(CRITIC_PRAISE)})`, "i");

function normalize(text) {
  let t = (text || "").toLowerCase();
  if (CYR_RE.test(t)) t = cyrillicToLatin(t).toLowerCase();
  return t.replace(APOS_RE, "'");
}

export function checkSecurityViolation(text) {
  if (!text) return false;
  const t = normalize(text);
  if (PHRASES.some(p => t.includes(p))) return true;
  if (RE_PREFIX.test(t) || RE_STRICT.test(t)) return true;
  return RE_GOV.test(t) && RE_CRIT.test(t);
}

export function checkHardViolation(text) {
  if (!text) return false;
  return RE_HARD.test(normalize(text));
}

export const SECURITY_WARNING =
  "⚠️ <b>So'rov qabul qilinmadi</b>\n\n" +
  "Bot faqat <b>tilshunoslik, ona tili, adabiyot va filologik ilmiy tadqiqot</b> yo'nalishida xizmat ko'rsatadi.\n" +
  "<blockquote>Diniy, siyosiy, ekstremistik mazmundagi, davlat, rahbar va amaldorlarni maqtash yoki tanqid qilish, " +
  "tuzum va qonunchilikni muhokama qilish, turli oqimlarga oid, shaxs qadr-qimmatini kamsituvchi, behayo hamda " +
  "boshqa sohalarga oid so'rovlar qat'iyan taqiqlanadi.</blockquote>\n" +
  "Iltimos, so'rovingizni til yoki adabiyotga oid qilib qayta yozing.";

export const BLOCKED_TEXT =
  "⛔ <b>Qoidabuzarlik sababli AI xizmatlari 24 soatga cheklandi.</b>\n" +
  "Bot faqat til va adabiyot yo'nalishida ishlaydi. Mashq va testlar (AI'siz) ishlashda davom etadi.";

export const STRIKE_LIMIT = 3;
export const STRIKE_WINDOW = 24 * 3600;

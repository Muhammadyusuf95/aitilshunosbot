const APOS_RE = /[ʻʼ‘’`´′]/g;

const TO_NEW = [
  ["O'", "Ö"], ["o'", "ö"], ["G'", "Ğ"], ["g'", "ğ"],
  ["SH", "Ş"], ["Sh", "Ş"], ["sH", "ş"], ["sh", "ş"],
  ["CH", "Ç"], ["Ch", "Ç"], ["cH", "ç"], ["ch", "ç"],
];

export function latinToNew(text) {
  if (!text) return "";
  let t = text.replace(APOS_RE, "'");
  for (const [oldS, newS] of TO_NEW) {
    t = t.split(oldS).join(newS);
  }
  return t;
}

const isUpper = (ch) => ch && ch !== ch.toLowerCase() && ch === ch.toUpperCase();
const isAlpha = (ch) => ch && /\p{L}/u.test(ch);

export function newToLatin(text) {
  if (!text) return "";
  let out = "";
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const nxt = text[i + 1] || "";
    const prv = i > 0 ? text[i - 1] : "";
    const caps = isUpper(nxt) || isUpper(prv);
    if (ch === "Ö") out += "O'";
    else if (ch === "ö") out += "o'";
    else if (ch === "Ğ") out += "G'";
    else if (ch === "ğ") out += "g'";
    else if (ch === "Ş") out += caps ? "SH" : "Sh";
    else if (ch === "ş") out += "sh";
    else if (ch === "Ç") out += caps ? "CH" : "Ch";
    else if (ch === "ç") out += "ch";
    else out += ch;
  }
  return out;
}

const CYR = {
  "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k",
  "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
  "х": "x", "ч": "ch", "ш": "sh", "э": "e", "ю": "yu", "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'",
  "ҳ": "h", "ё": "yo", "ц": "ts", "ъ": "'", "ь": "", "щ": "shch", "ы": "i",
};
const CYR_VOWELS = new Set([..."аоуиэеёюяўыъь"]);

export function cyrillicToLatin(text) {
  if (!text) return "";
  let out = "";
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const low = ch.toLowerCase();
    let lat;
    if (low === "е") {
      const prev = i > 0 ? text[i - 1].toLowerCase() : "";
      lat = (i === 0 || !isAlpha(prev) || CYR_VOWELS.has(prev)) ? "ye" : "e";
    } else if (low in CYR) {
      lat = CYR[low];
    } else {
      out += ch;
      continue;
    }
    if (isUpper(ch) && lat) {
      const nxt = text[i + 1] || "";
      lat = (lat.length > 1 && isUpper(nxt)) ? lat.toUpperCase() : lat[0].toUpperCase() + lat.slice(1);
    }
    out += lat;
  }
  return out;
}

const LAT = {
  "a": "а", "b": "б", "d": "д", "f": "ф", "g": "г", "h": "ҳ", "i": "и", "j": "ж", "k": "к", "l": "л",
  "m": "м", "n": "н", "o": "о", "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
  "x": "х", "y": "й", "z": "з", "c": "с", "w": "в",
};
const LAT_VOWELS = new Set([..."aeiou"]);

export function latinToCyrillic(text) {
  if (!text) return "";
  const t = text.replace(APOS_RE, "'");
  let out = "";
  let i = 0;
  const cased = (src, cyr) => isUpper(src) ? cyr.toUpperCase() : cyr;
  while (i < t.length) {
    const ch = t[i];
    const low = ch.toLowerCase();
    const two = t.slice(i, i + 2).toLowerCase();
    const prev = i > 0 ? t[i - 1].toLowerCase() : "";
    const wordStart = i === 0 || !(isAlpha(t[i - 1]) || t[i - 1] === "'");

    if (two === "o'") { out += cased(ch, "ў"); i += 2; continue; }
    if (two === "g'") { out += cased(ch, "ғ"); i += 2; continue; }
    if (two === "sh") { out += isUpper(ch) ? "Ш" : "ш"; i += 2; continue; }
    if (two === "ch") { out += isUpper(ch) ? "Ч" : "ч"; i += 2; continue; }
    if (two === "yo") { out += cased(ch, "ё"); i += 2; continue; }
    if (two === "yu") { out += cased(ch, "ю"); i += 2; continue; }
    if (two === "ya") { out += cased(ch, "я"); i += 2; continue; }
    if (two === "ye") { out += cased(ch, "е"); i += 2; continue; }
    if (two === "ts" && wordStart) { out += cased(ch, "ц"); i += 2; continue; }
    if (low === "e") { out += cased(ch, (wordStart || LAT_VOWELS.has(prev)) ? "э" : "е"); i += 1; continue; }
    if (ch === "'") {
      out += (i > 0 && isAlpha(t[i - 1]) && i + 1 < t.length && isAlpha(t[i + 1])) ? "ъ" : "'";
      i += 1; continue;
    }
    if (low in LAT) { out += cased(ch, LAT[low]); i += 1; continue; }
    out += ch;
    i += 1;
  }
  return out;
}

export const MODES = {
  lat2new: ["Lotin → Yangi alifbo (Ö Ğ Ş Ç)", latinToNew],
  new2lat: ["Yangi alifbo → Lotin", newToLatin],
  cyr2lat: ["Kirill → Lotin", cyrillicToLatin],
  lat2cyr: ["Lotin → Kirill", latinToCyrillic],
};

export function convert(mode, text) {
  return (MODES[mode]?.[1] || latinToNew)(text);
}

export function detectMode(text) {
  let cyr = 0, nw = 0;
  for (const c of text) {
    const l = c.toLowerCase();
    if ((l >= "а" && l <= "я") || "ўқғҳё".includes(l)) cyr++;
    if ("ÖöĞğŞşÇç".includes(c)) nw++;
  }
  if (cyr > Math.max(3, nw)) return "cyr2lat";
  if (nw > 0) return "new2lat";
  return "lat2new";
}

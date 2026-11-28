export const MAX_LEN = 4096;
export const CHUNK_SRC = 3200;

export function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function bar(done, total, width = 10, full = "▰", empty = "▱") {
  total = Math.max(1, total);
  const n = Math.max(0, Math.min(width, Math.round((width * done) / total)));
  return full.repeat(n) + empty.repeat(width - n);
}

export function card(title, subtitle = "", body = "", footer = "") {
  const parts = [`<b>${title}</b>`];
  if (subtitle) parts.push(`<i>${subtitle}</i>`);
  parts.push("━━━━━━━━━━━━━━━");
  let out = parts.join("\n");
  if (body) out += "\n\n" + body;
  if (footer) out += "\n\n" + footer;
  return out;
}

export function mdToHtml(text) {
  if (!text) return "";
  const holders = [];
  const hold = (s) => {
    holders.push(s);
    return `\x00${holders.length - 1}\x00`;
  };
  let t = text.replace(/\r\n/g, "\n");
  t = t.replace(/```[a-zA-Z0-9_+-]*\n?([\s\S]*?)```/g, (_, m) => hold(`<pre>${esc(m.replace(/^\n+|\n+$/g, ""))}</pre>`));
  t = t.replace(/`([^`\n]+)`/g, (_, m) => hold(`<code>${esc(m)}</code>`));
  t = esc(t);
  t = t.replace(/^\s*([-_*]\s*){3,}$/gm, "───────────");
  t = t.replace(/^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/gm, (_, m) => `<b>${m.trim()}</b>`);
  t = t.replace(/^(\s*)[\*\-•]\s+/gm, "$1• ");
  t = t.replace(/(\*\*|__)(?=\S)([\s\S]+?)(?<=\S)\1/g, "<b>$2</b>");
  t = t.replace(/(?<![\*\w])\*(?=[^\s\*])([^\*\n]+?)(?<=[^\s\*])\*(?![\*\w])/g, "<i>$1</i>");
  t = t.replace(/(?<![_\w])_(?=[^\s_])([^_\n]+?)(?<=[^\s_])_(?![_\w])/g, "<i>$1</i>");
  t = t.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>');
  t = t.replace(/((?:^&gt;[^\n]*(?:\n|$))+)/gm, (m) => {
    const inner = m.replace(/\n$/, "").replace(/^&gt;\s?/gm, "");
    return `<blockquote>${inner}</blockquote>\n`;
  });
  t = t.replace(/\*\*|__/g, "");
  t = t.replace(/\x00(\d+)\x00/g, (_, idx) => holders[Number(idx)]);
  return t.trim();
}

export function stripTags(s) {
  return String(s || "")
    .replace(/<\/?(?:b|i|u|s|a|code|pre|blockquote|tg-spoiler)[^>]*>/g, "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"');
}

export function splitSource(text, limit = CHUNK_SRC) {
  text = (text || "").trim();
  if (!text) return [];
  if (text.length <= limit) return [text];
  const chunks = [];
  let cur = "";
  for (const para of text.split(/\n{2,}/)) {
    let piece = para;
    while (piece.length > limit) {
      let cut = Math.max(
        piece.lastIndexOf("\n", limit),
        piece.lastIndexOf(". ", limit),
        piece.lastIndexOf(" ", limit)
      );
      cut = cut > Math.floor(limit / 3) ? cut : limit;
      const head = piece.slice(0, cut + 1);
      piece = piece.slice(cut + 1);
      if (cur) {
        chunks.push(cur);
        cur = "";
      }
      chunks.push(head.trim());
    }
    if (cur.length + piece.length + 2 <= limit) {
      cur = cur ? `${cur}\n\n${piece}` : piece;
    } else {
      if (cur) chunks.push(cur);
      cur = piece;
    }
  }
  if (cur) chunks.push(cur);
  return chunks.filter(c => c.trim());
}

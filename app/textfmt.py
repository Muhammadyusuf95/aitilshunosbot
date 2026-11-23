"""Telegram uchun matn formatlash: Markdown(AI) -> HTML, bo'laklash, xavfsiz yuborish.

Nega HTML? Eski `parse_mode="Markdown"` AI javobidagi `**qalin**`, `_`, `*` belgilarida tez-tez
"can't parse entities" xatosi berardi va 4096 belgidan uzun javoblar umuman yuborilmasdi.
"""
import html
import re
import time

from telebot.apihelper import ApiTelegramException

MAX_LEN = 4096
CHUNK_SRC = 3200  # manba matn bo'lagi; HTML teglari qo'shilgach ham 4096 dan oshmasligi uchun


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=False)


def bar(done, total, width=10, full="▰", empty="▱"):
    total = max(1, total)
    n = max(0, min(width, round(width * done / total)))
    return full * n + empty * (width - n)


def card(title, subtitle="", body="", footer=""):
    """Bot bo'ylab yagona vizual uslub: sarlavha, ixcham izoh, ajratgich, matn."""
    parts = [f"<b>{title}</b>"]
    if subtitle:
        parts.append(f"<i>{subtitle}</i>")
    parts.append("━━━━━━━━━━━━━━━")
    out = "\n".join(parts)
    if body:
        out += "\n\n" + body
    if footer:
        out += "\n\n" + footer
    return out


_CODE_BLOCK = re.compile(r"```[a-zA-Z0-9_+-]*\n?(.*?)```", re.S)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_HEADER = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.M)
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", re.S)
_ITALIC_STAR = re.compile(r"(?<![\*\w])\*(?=[^\s\*])([^\*\n]+?)(?<=[^\s\*])\*(?![\*\w])")
_ITALIC_UND = re.compile(r"(?<![_\w])_(?=[^\s_])([^_\n]+?)(?<=[^\s_])_(?![_\w])")
_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
_BULLET = re.compile(r"^(\s*)[\*\-•]\s+", re.M)
_QUOTE = re.compile(r"((?:^&gt;[^\n]*(?:\n|$))+)", re.M)
_HR = re.compile(r"^\s*([-_*]\s*){3,}$", re.M)


def md_to_html(text):
    """AI Markdown matnini Telegram HTML ga aylantiradi (xavfsiz: avval escape)."""
    if not text:
        return ""
    holders = []

    def hold(s):
        holders.append(s)
        return f"\x00{len(holders) - 1}\x00"

    t = text.replace("\r\n", "\n")
    t = _CODE_BLOCK.sub(lambda m: hold(f"<pre>{esc(m.group(1).strip(chr(10)))}</pre>"), t)
    t = _INLINE_CODE.sub(lambda m: hold(f"<code>{esc(m.group(1))}</code>"), t)
    t = esc(t)
    t = _HR.sub("───────────", t)
    t = _HEADER.sub(lambda m: f"<b>{m.group(1).strip()}</b>", t)
    t = _BULLET.sub(lambda m: f"{m.group(1)}• ", t)
    t = _BOLD.sub(lambda m: f"<b>{m.group(2)}</b>", t)
    t = _ITALIC_STAR.sub(lambda m: f"<i>{m.group(1)}</i>", t)
    t = _ITALIC_UND.sub(lambda m: f"<i>{m.group(1)}</i>", t)
    t = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', t)

    def quote(m):
        inner = re.sub(r"^&gt;\s?", "", m.group(1).rstrip("\n"), flags=re.M)
        return f"<blockquote>{inner}</blockquote>\n"

    t = _QUOTE.sub(quote, t)
    t = re.sub(r"\*\*|__", "", t)  # qolib ketgan juft bo'lmagan belgilarni olib tashlaymiz
    t = re.sub(r"\x00(\d+)\x00", lambda m: holders[int(m.group(1))], t)
    return t.strip()


def strip_tags(s):
    return html.unescape(re.sub(r"</?(?:b|i|u|s|a|code|pre|blockquote|tg-spoiler)[^>]*>", "", s))


def split_source(text, limit=CHUNK_SRC):
    """Uzun matnni abzats/qator chegarasida bo'laklaydi."""
    text = (text or "").strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks, cur = [], ""
    for para in re.split(r"\n{2,}", text):
        piece = para
        while len(piece) > limit:  # bitta abzats juda uzun bo'lsa
            cut = max(piece.rfind("\n", 0, limit), piece.rfind(". ", 0, limit), piece.rfind(" ", 0, limit))
            cut = cut if cut > limit // 3 else limit
            head, piece = piece[: cut + 1], piece[cut + 1:]
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(head.strip())
        if len(cur) + len(piece) + 2 <= limit:
            cur = f"{cur}\n\n{piece}" if cur else piece
        else:
            if cur:
                chunks.append(cur)
            cur = piece
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


def _is_parse_error(e):
    return isinstance(e, ApiTelegramException) and "parse entities" in str(e).lower()


def _retry_after(e):
    try:
        return int(e.result_json.get("parameters", {}).get("retry_after", 0))
    except Exception:
        return 0


def send_html(bot, chat_id, html_text, reply_markup=None, **kw):
    """HTML yuboradi; teg xatosi bo'lsa — oddiy matn sifatida qayta yuboradi; 429 da kutadi."""
    kw.setdefault("disable_web_page_preview", True)
    for attempt in range(3):
        try:
            return bot.send_message(chat_id, html_text[:MAX_LEN], parse_mode="HTML", reply_markup=reply_markup, **kw)
        except ApiTelegramException as e:
            if _is_parse_error(e):
                return bot.send_message(chat_id, strip_tags(html_text)[:MAX_LEN], reply_markup=reply_markup, **kw)
            ra = _retry_after(e)
            if e.error_code == 429 and attempt < 2:
                time.sleep(min(ra or 2, 15))
                continue
            raise


def send_long(bot, chat_id, md_text, reply_markup=None, already_html=False, **kw):
    """Uzun AI matnini bir necha xabarga bo'lib yuboradi; tugmalar oxirgi xabarda."""
    chunks = split_source(md_text)
    if not chunks:
        return None
    last = None
    for i, ch in enumerate(chunks):
        body = ch if already_html else md_to_html(ch)
        markup = reply_markup if i == len(chunks) - 1 else None
        last = send_html(bot, chat_id, body, reply_markup=markup, **kw)
        if len(chunks) > 1:
            time.sleep(0.3)
    return last


def edit_html(bot, chat_id, message_id, html_text, reply_markup=None):
    """Xabarni tahrirlaydi. Teg xatosida oddiy matn; 'o'zgarmagan' xatosini e'tiborsiz qoldiradi."""
    try:
        return bot.edit_message_text(
            html_text[:MAX_LEN], chat_id=chat_id, message_id=message_id,
            parse_mode="HTML", reply_markup=reply_markup, disable_web_page_preview=True,
        )
    except ApiTelegramException as e:
        msg = str(e).lower()
        if "not modified" in msg:
            return None
        if _is_parse_error(e):
            return bot.edit_message_text(
                strip_tags(html_text)[:MAX_LEN], chat_id=chat_id, message_id=message_id, reply_markup=reply_markup
            )
        raise

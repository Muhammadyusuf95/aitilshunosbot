"""Bo'limlar (hub), AI asboblar, aqlli javob, alifbo konvertori, so'z yasovchi qo'shimchalar, aqliy mashq."""
import random
import re
from collections import OrderedDict

from app import questions as qmod, translit
from app.content import SECTIONS, TOOLS
from app.handlers.common import bg, guard, on_cb, run_ai_text
from app.runtime import answer_cb, bot, clear_state, get_state, set_state, show
from app.textfmt import card, esc, send_html
from app.ui import kb, view_abit, view_conv_hub, view_section, view_sfx_hub

STATE_HANDLERS = {}
PHOTO_STATES = {}
PENDING_INPUT = OrderedDict()  # aqlli javob uchun vaqtinchalik matn/rasm
MAX_INPUT = 3500


def state_handler(action):
    def deco(fn):
        STATE_HANDLERS[action] = fn
        return fn
    return deco


def photo_state(action):
    def deco(fn):
        PHOTO_STATES[action] = fn
        return fn
    return deco


def download_photo(message):
    """Xabardagi eng sifatli rasmni baytlar sifatida yuklab oladi."""
    file_id = message.photo[-1].file_id
    return download_file_id(file_id)


def download_file_id(file_id):
    info = bot.get_file(file_id)
    data = bot.download_file(info.file_path)
    mime = "image/png" if str(info.file_path).lower().endswith(".png") else "image/jpeg"
    return data, mime


# ---------------- Hublar ----------------
@on_cb("hub:", "sec:")
def cb_hub(call):
    name = call.data.split(":", 1)[1]
    answer_cb(call)
    from app import ui
    views = {
        "abit": ui.view_abit, "cert": ui.view_cert, "topics": ui.view_topics_hub, "themes": ui.view_themes_hub,
    }
    if name in views:
        show(call, *views[name]())
    elif name in SECTIONS:
        show(call, *view_section(name))
    else:
        show(call, *view_abit())


@on_cb("conv_hub")
def cb_conv_hub(call):
    answer_cb(call)
    show(call, *view_conv_hub())


# ---------------- AI asboblar ----------------
@on_cb("tool:")
def cb_tool(call):
    key = call.data.split(":", 1)[1]
    tool = TOOLS.get(key)
    if not tool:
        answer_cb(call, "Asbob topilmadi", True)
        return
    answer_cb(call)
    set_state(call.from_user.id, "tool", key=key)
    hint = "\n\n<i>📷 Rasm sifatida ham yuborishingiz mumkin.</i>" if tool.get("photo") else ""
    send_html(bot, call.message.chat.id,
              f"<b>{tool['title']}</b>\n{tool['ask']}{hint}\n\n<i>Bekor qilish: /cancel yoki menyudan boshqa bo'lim.</i>")


@state_handler("tool")
def st_tool(message, st):
    key = st["data"]["key"]
    tool = TOOLS[key]
    text = (message.text or "").strip()
    if not text:
        send_html(bot, message.chat.id, "Iltimos, matn yuboring.")
        return
    clear_state(message.from_user.id)
    run_tool(message.chat.id, message.from_user, key, text[:MAX_INPUT])


def run_tool(chat_id, user, key, text):
    tool = TOOLS[key]
    prompt = tool["prompt"].replace("{input}", text)
    bg(run_ai_text, chat_id, user, prompt, tool["title"], key, text)


@photo_state("tool")
def st_tool_photo(message, st):
    key = st["data"]["key"]
    tool = TOOLS[key]
    if not tool.get("photo"):
        send_html(bot, message.chat.id, "Bu bo'lim faqat matn qabul qiladi. Iltimos, matn yuboring.")
        return
    clear_state(message.from_user.id)
    data = download_photo(message)
    prompt = ("Rasmdagi matnni avval aynan o'qing (## O'qilgan matn bo'limida keltiring), so'ng uni tekshiring.\n"
              + tool["prompt"].replace("{input}", "(rasmdagi matn)"))
    bg(run_ai_text, message.chat.id, message.from_user, prompt, tool["title"], key, None, data)


# ---------------- Aqlli javob: menyudan tashqari matn ----------------
def stash(kind, value):
    token = f"{random.randint(0, 16**5):05x}"
    PENDING_INPUT[token] = (kind, value)
    while len(PENDING_INPUT) > 300:
        PENDING_INPUT.popitem(last=False)
    return token


def smart_reply(message):
    text = (message.text or "").strip()
    if not text:
        return
    if not guard(message.chat.id, message.from_user, text):
        return
    token = stash("text", text[:MAX_INPUT])
    short = len(text) <= 40
    rows = []
    if short:
        rows.append([("📖 Izohi va imlosi", f"sm:{token}:izoh"), ("🔍 Etimologiyasi", f"sm:{token}:etim")])
        rows.append([("📜 Bayt sifatida tahlil", f"sm:{token}:gazal"), ("🔠 Alifbo", f"sm:{token}:conv")])
        head = f"«{esc(text[:40])}» bilan nima qilamiz?"
    else:
        rows.append([("✅ Imlo va uslub tekshiruvi", f"sm:{token}:imlo")])
        rows.append([("🛠 Shu matndan test tuzish", f"sm:{token}:passage"), ("✍️ Esse sifatida tekshirish", f"sm:{token}:esse")])
        rows.append([("🔠 Alifboni o'zgartirish", f"sm:{token}:conv")])
        head = "Matn qabul qilindi. Nima qilamiz?"
    send_html(bot, message.chat.id, f"<b>{head}</b>", reply_markup=kb(rows))


def smart_photo(message):
    token = stash("photo", message.photo[-1].file_id)
    rows = [[("✍️ Esse sifatida tekshirish", f"sm:{token}:esse")], [("✅ Imlo tekshiruvi", f"sm:{token}:imlo")]]
    send_html(bot, message.chat.id, "<b>📷 Rasm qabul qilindi. Nima qilamiz?</b>", reply_markup=kb(rows))


@on_cb("sm:")
def cb_smart(call):
    _, token, action = call.data.split(":", 2)
    item = PENDING_INPUT.get(token)
    if not item:
        answer_cb(call, "So'rov eskirgan. Matnni qayta yuboring.", True)
        return
    kind, value = item
    answer_cb(call)
    chat_id, user = call.message.chat.id, call.from_user

    if action == "conv":
        if kind != "text":
            return
        mode = translit.detect_mode(value)
        send_conversion(chat_id, mode, value)
        return
    if action == "passage":
        from app.handlers import tests
        tests.start_builder_from_passage(call, value)
        return
    if action == "esse":
        from app.handlers import essays
        essays.run_essay_check(chat_id, user, value if kind == "text" else None,
                               photo=download_file_id(value) if kind == "photo" else None)
        return
    if kind == "photo":
        data = download_file_id(value)
        tool = TOOLS["imlo"]
        prompt = ("Rasmdagi matnni avval aynan o'qing (## O'qilgan matn), so'ng uni tekshiring.\n"
                  + tool["prompt"].replace("{input}", "(rasmdagi matn)"))
        bg(run_ai_text, chat_id, user, prompt, tool["title"], "imlo", None, data)
        return
    if action in TOOLS:
        run_tool(chat_id, user, action, value)


# ---------------- Alifbo konvertori ----------------
def send_conversion(chat_id, mode, text):
    res = translit.convert(mode, text)
    label = translit.MODES[mode][0]
    send_html(bot, chat_id, f"🔠 <b>{label}</b>")
    for i in range(0, len(res), 4000):
        bot.send_message(chat_id, res[i:i + 4000])


@on_cb("conv:")
def cb_conv(call):
    mode = call.data.split(":", 1)[1]
    if mode not in translit.MODES:
        answer_cb(call)
        return
    answer_cb(call)
    set_state(call.from_user.id, "conv", mode=mode)
    send_html(bot, call.message.chat.id,
              f"🔠 <b>{translit.MODES[mode][0]}</b>\nMatnni yuboring. Bir necha matn ketma-ket yuborishingiz mumkin.\n"
              "<i>Tugatish: /cancel yoki menyudan boshqa bo'lim.</i>")


@state_handler("conv")
def st_conv(message, st):
    text = message.text or ""
    if not guard(message.chat.id, message.from_user, text):
        return
    send_conversion(message.chat.id, st["data"]["mode"], text)
    set_state(message.from_user.id, "conv", mode=st["data"]["mode"])  # rejimda qolamiz


# ---------------- So'z yasovchi qo'shimchalar ----------------
SFX_CATS = {
    "ot": ("ot_yasalishi", "Ot yasalishi"), "sifat": ("sifat_yasalishi", "Sifat yasalishi"),
    "fel": ("fel_yasalishi", "Fe'l yasalishi"), "ravish": ("ravish_yasalishi", "Ravish yasalishi"),
}
SFX_PAGE = 10


def _sfx_items(cat):
    return qmod.raw_bank().get("morfologiya_va_yasalish", {}).get(SFX_CATS[cat][0], [])


def _sfx_text(item):
    suffix = item.get("qo'shimcha", "")
    ex = ", ".join(item.get("misollar", [])[:5])
    return f"<b>{esc(suffix)}</b> <i>({esc(item.get('asos_turkum', ''))})</i> — {esc(ex)}"


@on_cb("sfx_hub")
def cb_sfx_hub(call):
    answer_cb(call)
    set_state(call.from_user.id, "sfx")
    show(call, *view_sfx_hub())


@on_cb("sfx:")
def cb_sfx(call):
    parts = call.data.split(":")
    cat = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    if cat not in SFX_CATS:
        answer_cb(call)
        return
    items = _sfx_items(cat)
    pages = max(1, (len(items) + SFX_PAGE - 1) // SFX_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = items[page * SFX_PAGE:(page + 1) * SFX_PAGE]
    body = "\n\n".join(_sfx_text(i) for i in chunk) or "Ma'lumot topilmadi."
    nav = []
    if page > 0:
        nav.append(("⬅️", f"sfx:{cat}:{page - 1}"))
    nav.append((f"{page + 1}/{pages}", "noop"))
    if page + 1 < pages:
        nav.append(("➡️", f"sfx:{cat}:{page + 1}"))
    markup = kb([nav, [("🔙 Qo'shimchalar", "sfx_hub")]])
    answer_cb(call)
    set_state(call.from_user.id, "sfx")
    show(call, card(f"🧩 {SFX_CATS[cat][1].upper()}", f"Jami {len(items)} ta qo'shimcha", body), markup)


@on_cb("noop", gated=False)
def cb_noop(call):
    answer_cb(call)


def _norm(s):
    return re.sub(r"[ʻʼ‘’`´′]", "'", s.lower()).strip()


def search_suffix(query):
    q = _norm(query).lstrip("-").strip()
    if not q:
        return []
    out = []
    data = qmod.raw_bank().get("morfologiya_va_yasalish", {})
    for cat, (key, label) in SFX_CATS.items():
        for item in data.get(key, []):
            variants = [v.strip().lstrip("-") for v in re.split(r"[/,]", _norm(item.get("qo'shimcha", "")))]
            examples = [_norm(m).split(" ")[0] for m in item.get("misollar", [])]
            if q in variants:
                out.append((0, label, item))
            elif q in examples:
                out.append((1, label, item))
    out.sort(key=lambda x: x[0])
    return out


@state_handler("sfx")
def st_sfx(message, st):
    q = (message.text or "").strip()
    res = search_suffix(q)
    if not res:
        send_html(bot, message.chat.id,
                  f"🔎 «{esc(q[:40])}» bo'yicha natija topilmadi.\n<i>Qo'shimchani (<code>-chi</code>) yoki jadvaldagi "
                  "so'zni yozib ko'ring.</i>")
    else:
        lines = [f"<b>{label}</b> · {_sfx_text(item)}" for _, label, item in res[:12]]
        more = f"\n\n<i>…yana {len(res) - 12} ta natija bor.</i>" if len(res) > 12 else ""
        send_html(bot, message.chat.id, card("🔎 NATIJALAR", f"«{esc(q[:40])}»", "\n\n".join(lines) + more))
    set_state(message.from_user.id, "sfx")


# ---------------- Aqliy mashq (ochiq topshiriqlar) ----------------
@on_cb("open_next")
def cb_open_next(call):
    tasks = qmod.raw_bank().get("open_tasks", [])
    answer_cb(call)
    if not tasks:
        send_html(bot, call.message.chat.id, "Hozircha topshiriqlar yo'q.")
        return
    i = random.randrange(len(tasks))
    markup = kb([[("👁 Javobni ko'rish", f"open_ans:{i}")], [("➡️ Boshqa topshiriq", "open_next")]])
    send_html(bot, call.message.chat.id, card("🧠 AQLIY MASHQ", "Avval o'zingiz o'ylab ko'ring",
                                              esc(tasks[i]["task"])), reply_markup=markup)


@on_cb("open_ans:")
def cb_open_ans(call):
    tasks = qmod.raw_bank().get("open_tasks", [])
    i = int(call.data.split(":")[1])
    answer_cb(call)
    if 0 <= i < len(tasks):
        t = tasks[i]
        show(call, card("🧠 AQLIY MASHQ", "Javob", f"{esc(t['task'])}\n\n✅ <b>Javob:</b> {esc(t['answer'])}"),
             kb([[("➡️ Boshqa topshiriq", "open_next")]]))

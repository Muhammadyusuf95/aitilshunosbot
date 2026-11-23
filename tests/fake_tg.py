"""Telegram API'ni soxtalashtirish: haqiqiy tarmoqsiz handlerlarni sinash."""
import itertools, json, os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["TELEGRAM_TOKEN"] = "123:TEST"
os.environ["GEMINI_API_KEY"] = "x"
os.environ["PUBLIC_URL"] = "https://example.test"
from telebot import apihelper, types

CALLS = []
_mid = itertools.count(100)
CHAT_USER = {"id": 777, "is_bot": False, "first_name": "Test"}


def _msg(chat_id, text=None, extra=None):
    chat = {"id": chat_id if isinstance(chat_id, int) else -100500, "type": "private" if isinstance(chat_id, int) and chat_id > 0 else "supergroup", "title": "G"}
    m = {"message_id": next(_mid), "date": int(time.time()), "chat": chat, "from": {"id": 1, "is_bot": True, "first_name": "bot"}}
    if text is not None:
        m["text"] = text
    if extra:
        m.update(extra)
    return m


def fake_request(token, method_name, method="get", params=None, files=None, **kw):
    params = params or {}
    CALLS.append((method_name, dict(params)))
    if method_name in ("sendMessage", "editMessageText"):
        return _msg(params.get("chat_id", 1), params.get("text"))
    if method_name == "sendPoll":
        return _msg(params.get("chat_id"), None, {"poll": {"id": f"poll{next(_mid)}", "question": params.get("question", ""), "options": [], "total_voter_count": 0, "is_closed": False, "is_anonymous": False, "type": "quiz", "allows_multiple_answers": False}})
    if method_name == "getMe":
        return {"id": 999, "is_bot": True, "first_name": "Bot", "username": "aitilshunosbot"}
    if method_name == "getChatMember":
        return {"status": "member", "user": CHAT_USER}
    if method_name == "getChat":
        return {"id": -100500, "type": "supergroup", "title": "Guruh"}
    if method_name == "getFile":
        return {"file_id": "f", "file_unique_id": "fu", "file_path": "photos/a.jpg"}
    if method_name == "sendDocument":
        return _msg(params.get("chat_id", 1), "doc")
    return True


apihelper._make_request = fake_request
apihelper.CUSTOM_REQUEST_SENDER = None


def texts(method=("sendMessage", "editMessageText")):
    return [c[1].get("text", "") for c in CALLS if c[0] in method]


def reset():
    CALLS.clear()


def settle(timeout=5):
    t0 = time.time()
    last = -1
    while time.time() - t0 < timeout:
        n = len(CALLS)
        time.sleep(0.25)
        busy = [t for t in threading.enumerate() if t.daemon and t.name.startswith("Thread-") and t.is_alive() and t is not threading.current_thread() and "bg" in repr(getattr(t, "_target", ""))]
        if n == len(CALLS) and not busy:
            return

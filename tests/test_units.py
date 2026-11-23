import tests.fake_tg  # noqa
from app.textfmt import md_to_html, split_source, strip_tags
from app.security import check_security_violation as sec
from app import translit
from app.handlers.group import poll_payload

def test_md():
    h = md_to_html("## Bosh\n**a** va *b* snake_case_word <x> & 2*3\n- bir\n```\ncode <b>\n```")
    assert "<b>Bosh</b>" in h and "<b>a</b>" in h and "<i>b</i>" in h
    assert "snake_case_word" in h and "&lt;x&gt;" in h and "• bir" in h and "<pre>code &lt;b&gt;</pre>" in h

def test_split_long():
    text = "\n\n".join(["Gap. " * 200] * 8)
    parts = split_source(text)
    assert len(parts) > 1 and all(len(md_to_html(p)) < 4096 for p in parts)

def test_security():
    assert sec("din haqida") and sec("Prezident") and not sec("hikoyat va rivoyat") and not sec("maqsadini yodingizda tuting")

def test_translit_roundtrip():
    assert translit.new_to_latin(translit.latin_to_new("O'zbek shahar choy")) == "O'zbek shahar choy"
    assert translit.cyrillic_to_latin("Шаҳар ёзув") == "Shahar yozuv"
    assert translit.latin_to_cyrillic("shahar yozuv") == "шаҳар ёзув"

def test_poll_payload_long():
    q = {"question": "S" * 400, "options": ["a" * 130, "b", "c", "d"], "correct_option_id": 0, "explanation": "e" * 300}
    p = poll_payload(q, 1, 5, 30)
    assert p["card"] and p["options"] == list("ABCD") and len(p["question"]) <= 300 and len(p["explanation"]) <= 200

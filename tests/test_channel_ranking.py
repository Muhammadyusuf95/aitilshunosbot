"""Kanal testi reytingi: savollar saqlanadi, bot ichida ishlaganlar reytingga kiradi, test reytinglari alohida."""
from tests import fake_tg  # noqa: F401  (test muhitini app.config yuklanishidan oldin o'rnatadi)
import os
import tempfile
import types

from app.db import Database as DB


def _growth():
    from app.handlers import growth
    return growth


def _db():
    path = os.path.join(tempfile.mkdtemp(), "t.sqlite3")
    return DB(sqlite_path=path)


QS = [{"question": f"Q{i}", "options": ["a", "b", "c", "d"], "correct_option_id": 0, "explanation": ""}
      for i in range(3)]


def test_channel_test_saved_and_ranked_by_correct_then_time():
    db = _db()
    tid = db.add_channel_test("№1 BMB 30 talik test", QS, 30)
    assert db.get_channel_test(tid)["questions"] == QS
    db.save_channel_result(tid, 1, "Ali", 3, 3, 40.0)
    db.save_channel_result(tid, 2, "Vali", 3, 3, 25.0)   # teng ball, tezroq -> birinchi
    db.save_channel_result(tid, 3, "Gani", 2, 3, 10.0)
    assert db.channel_rank(tid, 2)["rank"] == 1
    assert db.channel_rank(tid, 1)["rank"] == 2
    assert db.channel_rank(tid, 3)["rank"] == 3
    assert db.channel_rank(tid, 99) is None
    assert db.channel_count(tid) == 3


def test_first_attempt_only_and_tests_do_not_mix():
    db = _db()
    t1 = db.add_channel_test("Test A", QS, 30)
    t2 = db.add_channel_test("Test B", QS, 30)
    assert db.save_channel_result(t1, 5, "Sami", 3, 3, 9.0) is True
    assert db.save_channel_result(t1, 5, "Sami", 0, 3, 1.0) is False  # qayta urinish hisobga olinmaydi
    assert db.channel_rank(t1, 5)["correct"] == 3
    assert db.channel_rank(t2, 5) is None                             # boshqa testda ishtirok etmagan
    assert db.channel_count(t2) == 0


def test_rank_updates_as_more_people_play(monkeypatch):
    db = _db()
    tid = db.add_channel_test("Test C", QS, 30)
    db.save_channel_result(tid, 1, "Ali", 2, 3, 20.0)
    assert db.channel_rank(tid, 1)["rank"] == 1
    db.save_channel_result(tid, 2, "Vali", 3, 3, 30.0)   # yangi ishtirokchi yuqoriga chiqdi
    assert db.channel_rank(tid, 1)["rank"] == 2


def test_bot_session_records_channel_result_and_rank(monkeypatch):
    growth = _growth()
    db = _db()
    monkeypatch.setattr(growth, "get_db", lambda: db)
    tid = db.add_channel_test("Test D", QS, 30)
    s = types.SimpleNamespace(ctx={"channel_test": tid}, total=3, uid=7, name="Ali", correct=3, time_spent=12.0)
    text = growth._channel_session_done(s, {"answered": 3})
    assert "#1 o'rin" in text
    assert db.channel_rank(tid, 7)["rank"] == 1
    # yarim yakunlangan test reytingga kirmaydi
    partial = types.SimpleNamespace(ctx={"channel_test": tid}, total=3, uid=8, name="Vali", correct=3, time_spent=5.0)
    assert "oxirigacha" in growth._channel_session_done(partial, {"answered": 1})
    assert db.channel_rank(tid, 8) is None


def test_channel_view_shows_board_and_own_rank(monkeypatch):
    growth = _growth()
    db = _db()
    monkeypatch.setattr(growth, "get_db", lambda: db)
    tid = db.add_channel_test("Test E", QS, 30)
    db.save_channel_result(tid, 1, "Ali", 3, 3, 10.0)
    html, mk = growth.channel_test_view(2, tid)
    assert "Ali" in html and "Siz hali bu testda ishtirok etmagansiz" in html
    html, mk = growth.channel_test_view(1, tid)
    assert "Sizning o'rningiz: <b>#1</b>" in html
    assert growth.channel_test_view(1, 9999) is None

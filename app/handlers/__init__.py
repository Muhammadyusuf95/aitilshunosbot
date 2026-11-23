def register_all():
    """Handlerlarni tartib bilan ulaydi (core — eng oxirida: u hamma narsani ushlovchi yo'naltiruvchi)."""
    from app.handlers import common, tools, essays, tests, group, profile, admin, inline, growth, core  # noqa: F401

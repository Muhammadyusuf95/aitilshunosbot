CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT DEFAULT '',
    first_name TEXT DEFAULT '',
    points INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    last_active TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    referred_by INTEGER,
    invites INTEGER DEFAULT 0,
    daily_done TEXT,
    reminders INTEGER DEFAULT 1,
    exam_date TEXT,
    exam_name TEXT,
    quiz_alerts INTEGER DEFAULT 0,
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT,
    mode TEXT,
    title TEXT,
    correct INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    duration REAL DEFAULT 0,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_qr_user ON quiz_results(user_id);
CREATE INDEX IF NOT EXISTS idx_qr_created ON quiz_results(created_at);

CREATE TABLE IF NOT EXISTS mistakes (
    user_id INTEGER NOT NULL,
    qkey TEXT NOT NULL,
    payload TEXT,
    created_at TEXT,
    PRIMARY KEY (user_id, qkey)
);

CREATE TABLE IF NOT EXISTS badges (
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    earned_at TEXT,
    PRIMARY KEY (user_id, code)
);

CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT
);

CREATE TABLE IF NOT EXISTS user_states (
    user_id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    data TEXT DEFAULT '{}',
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_items (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS classes (
    code TEXT PRIMARY KEY,
    teacher_id INTEGER NOT NULL,
    name TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS class_members (
    code TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT,
    joined_at TEXT,
    PRIMARY KEY (code, user_id)
);

CREATE TABLE IF NOT EXISTS class_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    title TEXT,
    questions TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS class_results (
    test_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT,
    correct INTEGER,
    total INTEGER,
    duration REAL,
    created_at TEXT,
    PRIMARY KEY (test_id, user_id)
);

CREATE TABLE IF NOT EXISTS channel_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    questions TEXT,
    duration INTEGER DEFAULT 30,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS channel_results (
    test_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT,
    correct INTEGER,
    total INTEGER,
    duration REAL,
    created_at TEXT,
    PRIMARY KEY (test_id, user_id)
);

CREATE TABLE IF NOT EXISTS poll_map (
    poll_id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

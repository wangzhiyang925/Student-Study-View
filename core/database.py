"""数据库层（安卓版）：与桌面版逻辑一致，仅数据库路径来自 storage.DB_PATH。"""
import os
import sqlite3
import hashlib
import secrets
from datetime import date, datetime, timedelta

from . import storage

DB_PATH = storage.DB_PATH

# 默认科目（首次建库时种入；之后管理员可在 App 内增删）
DEFAULT_SUBJECTS = [("语文", "#FF6B6B"), ("数学", "#4D96FF"), ("英语", "#06D6A0")]
# 兜底常量（仅在数据库尚不可用时使用）；实际科目请用 subject_names()
SUBJECTS = [s[0] for s in DEFAULT_SUBJECTS]
# 新增科目自动分配的备选配色
SUBJECT_PALETTE = ["#FFD166", "#9B5DE5", "#F15BB5", "#00BBF9", "#FB5607",
                   "#8AC926", "#FF924C", "#118AB2"]


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------- 密码处理 ----------------
def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 salt.encode("utf-8"), 100_000)
    return f"{salt}${digest.hex()}"


def _verify_password(password, stored):
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(_hash_password(password, salt), stored)


# ---------------- 初始化 ----------------
def init_db():
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password      TEXT NOT NULL,
                display_name  TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'student',
                grade         TEXT DEFAULT '',
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS checkins (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                subject     TEXT NOT NULL,
                study_date  TEXT NOT NULL,
                minutes     INTEGER NOT NULL DEFAULT 0,
                content     TEXT DEFAULT '',
                mood        TEXT DEFAULT '😀',
                created_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS recipients (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT UNIQUE NOT NULL,
                note        TEXT DEFAULT '',
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                color       TEXT DEFAULT '#4D96FF',
                sort        INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS checkin_media (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                checkin_id  INTEGER NOT NULL,
                mtype       TEXT NOT NULL,
                path        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (checkin_id) REFERENCES checkins(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()

        # 种入默认科目
        cur = conn.execute("SELECT COUNT(*) AS c FROM subjects")
        if cur.fetchone()["c"] == 0:
            for i, (name, color) in enumerate(DEFAULT_SUBJECTS):
                conn.execute("INSERT OR IGNORE INTO subjects (name, color, sort) VALUES (?,?,?)",
                             (name, color, i))
            conn.commit()

        cur = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin'")
        if cur.fetchone()["c"] == 0:
            conn.execute(
                "INSERT INTO users (username, password, display_name, role, grade, created_at)"
                " VALUES (?,?,?,?,?,?)",
                ("admin", _hash_password("admin123"), "管理员", "admin", "",
                 datetime.now().isoformat(timespec="seconds")),
            )
            conn.commit()

        from .config import load_config
        for email in load_config().get("default_recipients", []):
            conn.execute(
                "INSERT OR IGNORE INTO recipients (email, note, created_at) VALUES (?,?,?)",
                (email, "默认收件人", datetime.now().isoformat(timespec="seconds")),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------- 用户 ----------------
def create_user(username, password, display_name, role="student", grade=""):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO users (username, password, display_name, role, grade, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (username.strip(), _hash_password(password), display_name.strip(),
             role, grade.strip(), datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return conn.execute("SELECT id FROM users WHERE username=?",
                            (username.strip(),)).fetchone()["id"]
    except sqlite3.IntegrityError:
        raise ValueError("用户名已存在，请换一个名字～")
    finally:
        conn.close()


def authenticate(username, password):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE username=?",
                           (username.strip(),)).fetchone()
        if row and _verify_password(password, row["password"]):
            return _user_to_dict(row)
        return None
    finally:
        conn.close()


def change_password(user_id, new_password):
    conn = _connect()
    try:
        conn.execute("UPDATE users SET password=? WHERE id=?",
                    (_hash_password(new_password), user_id))
        conn.commit()
    finally:
        conn.close()


def list_students():
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM users WHERE role='student' ORDER BY display_name"
        ).fetchall()
        return [_user_to_dict(r) for r in rows]
    finally:
        conn.close()


def _user_to_dict(row):
    return {
        "id": row["id"], "username": row["username"],
        "display_name": row["display_name"], "role": row["role"],
        "grade": row["grade"], "created_at": row["created_at"],
    }


# ---------------- 打卡 ----------------
def add_checkin(user_id, subject, minutes, content, mood="😀", study_date=None):
    if subject not in subject_names():
        raise ValueError("科目无效")
    if study_date is None:
        study_date = date.today().isoformat()
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO checkins (user_id, subject, study_date, minutes, content, mood, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (user_id, subject, study_date, int(minutes), content.strip(), mood,
             datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_checkins(user_id, start_date=None, end_date=None, subject=None):
    conn = _connect()
    try:
        sql = "SELECT * FROM checkins WHERE user_id=?"
        params = [user_id]
        if start_date:
            sql += " AND study_date>=?"; params.append(start_date)
        if end_date:
            sql += " AND study_date<=?"; params.append(end_date)
        if subject:
            sql += " AND subject=?"; params.append(subject)
        sql += " ORDER BY study_date DESC, created_at DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def update_checkin(checkin_id, user_id, subject, minutes, content, mood, study_date):
    if subject not in subject_names():
        raise ValueError("科目无效")
    conn = _connect()
    try:
        conn.execute(
            "UPDATE checkins SET subject=?, minutes=?, content=?, mood=?, study_date=?"
            " WHERE id=? AND user_id=?",
            (subject, int(minutes), content.strip(), mood, study_date,
             checkin_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_checkin(checkin_id, user_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM checkins WHERE id=? AND user_id=?",
                    (checkin_id, user_id))
        conn.commit()
    finally:
        conn.close()


def has_checked_in_today(user_id, subject, study_date=None):
    if study_date is None:
        study_date = date.today().isoformat()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM checkins WHERE user_id=? AND subject=? AND study_date=?",
            (user_id, subject, study_date)).fetchone()
        return row["c"] > 0
    finally:
        conn.close()


# ---------------- 统计 ----------------
def subject_summary(user_id, start_date, end_date):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT subject, COUNT(*) AS times, COALESCE(SUM(minutes),0) AS minutes"
            " FROM checkins WHERE user_id=? AND study_date>=? AND study_date<=?"
            " GROUP BY subject", (user_id, start_date, end_date)).fetchall()
        result = {s: {"times": 0, "minutes": 0} for s in subject_names()}
        for r in rows:
            result[r["subject"]] = {"times": r["times"], "minutes": r["minutes"]}
        return result
    finally:
        conn.close()


def streak_days(user_id):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT study_date FROM checkins WHERE user_id=? ORDER BY study_date DESC",
            (user_id,)).fetchall()
        dates = {r["study_date"] for r in rows}
        streak = 0
        cur = date.today()
        if cur.isoformat() not in dates:
            cur = cur - timedelta(days=1)
        while cur.isoformat() in dates:
            streak += 1
            cur = cur - timedelta(days=1)
        return streak
    finally:
        conn.close()


# ---------------- 科目（类目）----------------
def list_subjects():
    """返回 [{id, name, color, sort}]，按 sort、id 排序。"""
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM subjects ORDER BY sort, id").fetchall()]
    finally:
        conn.close()


def subject_names():
    """返回当前科目名称列表；数据库异常时回退到默认。"""
    try:
        names = [s["name"] for s in list_subjects()]
        return names or SUBJECTS
    except Exception:
        return SUBJECTS


def subject_color_map():
    """返回 {name: color_hex}。"""
    try:
        return {s["name"]: s["color"] for s in list_subjects()}
    except Exception:
        return {n: c for n, c in DEFAULT_SUBJECTS}


def add_subject(name, color=None):
    name = name.strip()
    if not name:
        raise ValueError("科目名称不能为空")
    conn = _connect()
    try:
        if color is None:
            cnt = conn.execute("SELECT COUNT(*) AS c FROM subjects").fetchone()["c"]
            color = SUBJECT_PALETTE[cnt % len(SUBJECT_PALETTE)]
        try:
            conn.execute("INSERT INTO subjects (name, color, sort) VALUES (?,?,?)",
                         (name, color,
                          conn.execute("SELECT COALESCE(MAX(sort),0)+1 AS s FROM subjects").fetchone()["s"]))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("该科目已存在")
    finally:
        conn.close()


def delete_subject(subject_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------- 打卡附件（照片 / 录音 / 视频）----------------
def add_media(checkin_id, mtype, path):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO checkin_media (checkin_id, mtype, path, created_at) VALUES (?,?,?,?)",
            (checkin_id, mtype, path, datetime.now().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()


def get_media(checkin_id):
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM checkin_media WHERE checkin_id=? ORDER BY id", (checkin_id,)).fetchall()]
    finally:
        conn.close()


def last_checkin_id(user_id):
    """取该用户最近一条打卡的 id（用于打卡后挂附件）。"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id FROM checkins WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


# ---------------- 收件人 ----------------
def list_recipients():
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM recipients ORDER BY created_at").fetchall()]
    finally:
        conn.close()


def add_recipient(email, note=""):
    conn = _connect()
    try:
        conn.execute("INSERT OR IGNORE INTO recipients (email, note, created_at) VALUES (?,?,?)",
                    (email.strip(), note.strip(), datetime.now().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()


def delete_recipient(recipient_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM recipients WHERE id=?", (recipient_id,))
        conn.commit()
    finally:
        conn.close()

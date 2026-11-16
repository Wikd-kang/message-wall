# -*- coding: utf-8 -*-
"""
数据访问层
==========
所有和 SQLite 打交道的代码都收在这里，app.py 只负责业务流程。
这样以后换数据库（比如换成 MySQL/PostgreSQL）只要改这一个文件。
"""
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 允许用环境变量指定数据库位置（部署到服务器时用得上）
DB_PATH = os.environ.get("MW_DB_PATH") or os.path.join(BASE_DIR, "wall.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS message (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    author_name TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_message_created ON message (created_at DESC);
"""


def get_conn():
    """取一个数据库连接。row_factory 让查询结果可以按列名取值。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """建表。每次启动调用一次，表已存在时什么也不做。"""
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------
# 用户
# --------------------------------------------------------------------------
def create_user(username, password_hash, is_admin=0):
    """新建用户，返回新用户 id。用户名已存在时会抛 sqlite3.IntegrityError。"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) "
            "VALUES (?, ?, ?, ?)",
            (username, password_hash, is_admin, _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user_by_name(username):
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()


def get_user(uid):
    conn = get_conn()
    try:
        return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    finally:
        conn.close()


def count_users():
    conn = get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# 留言
# --------------------------------------------------------------------------
def list_messages(keyword=None, page=1, per_page=10):
    """分页取留言，最新的在前。keyword 非空时按内容模糊搜索。"""
    offset = (page - 1) * per_page
    sql = (
        "SELECT m.*, u.username AS owner "
        "FROM message m LEFT JOIN users u ON u.id = m.user_id "
    )
    params = []
    if keyword:
        sql += "WHERE m.content LIKE ? OR m.author_name LIKE ? "
        like = "%" + keyword + "%"
        params += [like, like]
    sql += "ORDER BY m.id DESC LIMIT ? OFFSET ?"
    params += [per_page, offset]

    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def count_messages(keyword=None):
    sql = "SELECT COUNT(*) FROM message"
    params = []
    if keyword:
        sql += " WHERE content LIKE ? OR author_name LIKE ?"
        params = ["%" + keyword + "%", "%" + keyword + "%"]
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def add_message(user_id, author_name, content):
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO message (user_id, author_name, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, author_name, content, _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_message(mid):
    conn = get_conn()
    try:
        return conn.execute("SELECT * FROM message WHERE id = ?", (mid,)).fetchone()
    finally:
        conn.close()


def delete_message(mid):
    """删除留言，返回实际删除的行数（0 表示这条不存在）。"""
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM message WHERE id = ?", (mid,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def all_messages_for_export():
    """导出用：一次取全部留言（不分页）。"""
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT m.id, m.author_name, m.content, m.created_at, u.username AS owner "
            "FROM message m LEFT JOIN users u ON u.id = m.user_id "
            "ORDER BY m.id DESC"
        ).fetchall()
    finally:
        conn.close()

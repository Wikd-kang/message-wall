# -*- coding: utf-8 -*-
"""
认证相关的小工具
================
- 密码只存哈希，绝不存明文（这是这个项目相对「教学版」最重要的改动）
- login_required / admin_required 两个装饰器包住需要权限的视图
"""
from functools import wraps

from flask import flash, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db


def hash_password(raw: str) -> str:
    """生成密码哈希。werkzeug 默认用 pbkdf2，salt 自动带在里面。"""
    return generate_password_hash(raw)


def verify_password(stored_hash: str, raw: str) -> bool:
    return check_password_hash(stored_hash, raw)


def current_user():
    """从 session 取当前登录用户（每次都回数据库拿最新的，避免 session 过期不干净）。"""
    uid = session.get("uid")
    if not uid:
        return None
    return db.get_user(uid)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("请先登录")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            flash("请先登录")
            return redirect(url_for("login", next=request.path))
        if not user["is_admin"]:
            flash("这个页面只有管理员能看")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapper

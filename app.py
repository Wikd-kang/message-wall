# -*- coding: utf-8 -*-
"""
留言板系统（Message Wall）
=========================
一个可以直接交付给客户的小型留言/反馈收集系统。

相对「教学作业版」多了这些：
  1. 用户注册 / 登录 / 登出，密码只存哈希
  2. 留言归属到人，只有作者本人或管理员能删
  3. 首页分页 + 搜索
  4. 管理员后台：查看全部、批量导出 Excel（openpyxl）

运行：
    pip install -r requirements.txt
    python app.py
    浏览器打开 http://127.0.0.1:5000
"""
import os
import secrets
from datetime import datetime

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

import auth
import db
import export

app = Flask(__name__)
# 生产环境务必用环境变量固定 MW_SECRET_KEY，否则每次重启会话都会失效
app.secret_key = os.environ.get("MW_SECRET_KEY") or secrets.token_hex(16)

app.config["PER_PAGE"] = 10
app.config["MAX_NAME"] = 20
app.config["MAX_CONTENT"] = 500


# --------------------------------------------------------------------------
# 请求钩子：把当前用户塞进 g，模板里可以直接用 current_user
# --------------------------------------------------------------------------
@app.before_request
def load_user():
    g.user = auth.current_user()


@app.context_processor
def inject_globals():
    return {"current_user": g.get("user")}


# --------------------------------------------------------------------------
# 首页：分页 + 搜索
# --------------------------------------------------------------------------
@app.route("/")
def index():
    kw = request.args.get("kw", "").strip()[:50]

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    per_page = app.config["PER_PAGE"]
    total = db.count_messages(kw)
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    messages = db.list_messages(kw, page, per_page)

    return render_template(
        "index.html",
        messages=messages,
        kw=kw,
        total=total,
        page=page,
        pages=pages,
    )


# --------------------------------------------------------------------------
# 发布留言（必须登录）
# --------------------------------------------------------------------------
@app.route("/post", methods=["GET", "POST"])
@auth.login_required
def post():
    content = ""
    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        if not content:
            flash("留言内容不能为空")
        elif len(content) > app.config["MAX_CONTENT"]:
            flash("留言不能超过 %d 个字" % app.config["MAX_CONTENT"])
        else:
            user = auth.current_user()
            db.add_message(user["id"], user["username"], content)
            flash("发布成功")
            return redirect(url_for("index"))
    return render_template("form.html", content=content)


# --------------------------------------------------------------------------
# 删除留言：只有作者本人或管理员可以删
# --------------------------------------------------------------------------
@app.route("/delete/<int:mid>", methods=["POST"])
@auth.login_required
def delete(mid):
    msg = db.get_message(mid)
    if msg is None:
        flash("留言不存在，可能已经被删掉了")
        return redirect(url_for("index"))

    user = auth.current_user()
    if msg["user_id"] != user["id"] and not user["is_admin"]:
        flash("你只能删除自己的留言")
        return redirect(url_for("index"))

    db.delete_message(mid)
    flash("已删除")
    return redirect(request.referrer or url_for("index"))


# --------------------------------------------------------------------------
# 注册 / 登录 / 登出
# --------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if auth.current_user():
        return redirect(url_for("index"))

    error = ""
    username = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if not (3 <= len(username) <= 20):
            error = "用户名长度要在 3 到 20 个字符之间"
        elif len(password) < 6:
            error = "密码至少 6 位"
        elif password != confirm:
            error = "两次输入的密码不一样"
        elif db.get_user_by_name(username) is not None:
            error = "这个用户名已经被注册了"
        else:
            db.create_user(username, auth.hash_password(password))
            flash("注册成功，请登录")
            return redirect(url_for("login"))

    return render_template("register.html", error=error, username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    if auth.current_user():
        return redirect(url_for("index"))

    error = ""
    username = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = db.get_user_by_name(username)
        if user is not None and auth.verify_password(user["password_hash"], password):
            session.clear()
            session["uid"] = user["id"]
            flash("欢迎回来，%s" % user["username"])
            # 只允许跳回本站路径，防止被拿去做开放重定向
            nxt = request.args.get("next") or request.form.get("next") or ""
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for("index"))
        error = "账号或密码不对"

    return render_template("login.html", error=error, username=username)


@app.route("/logout")
def logout():
    session.clear()
    flash("已经退出登录")
    return redirect(url_for("index"))


# --------------------------------------------------------------------------
# 管理员后台
# --------------------------------------------------------------------------
@app.route("/admin")
@auth.admin_required
def admin():
    rows = db.all_messages_for_export()
    return render_template("admin.html", rows=rows, total=len(rows))


@app.route("/admin/export")
@auth.admin_required
def export_xlsx():
    rows = db.all_messages_for_export()
    buf = export.messages_to_xlsx(rows)
    filename = "留言导出_%s.xlsx" % datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


# --------------------------------------------------------------------------
# 错误页
# --------------------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


# --------------------------------------------------------------------------
# 初始化：建表 + 首次启动自动建一个管理员
# --------------------------------------------------------------------------
def bootstrap():
    db.init_db()
    if db.count_users() == 0:
        admin_name = os.environ.get("MW_ADMIN_USER", "admin")
        admin_pwd = os.environ.get("MW_ADMIN_PASSWORD", "admin123")
        db.create_user(admin_name, auth.hash_password(admin_pwd), is_admin=1)
        print(" * 已创建管理员：%s / %s（请尽快改掉）" % (admin_name, admin_pwd))
    # 演示模式：线上给人点开看的时候不至于是一块空板
    if os.environ.get("MW_SEED_DEMO") == "1" and db.count_messages() == 0:
        seed_demo()


# 演示数据（MW_SEED_DEMO=1 时使用）
DEMO_USERS = [
    ("xiaolin", "lin123456"),
    ("amei", "amei123456"),
    ("laozhou", "zhou123456"),
]

DEMO_MESSAGES = [
    ("xiaolin", "打印机又卡纸了，二楼那台，纸好像受潮了。"),
    ("amei", "年会抽奖能不能别用那个摇号软件了，去年抽到一半崩了。"),
    ("laozhou", "建议给会议室加个预约白板，现在都是群里抢，经常撞车。"),
    ("xiaolin", "下次团建想去露营，不想再爬山了，上次腿疼了三天。"),
    ("amei", "打卡机偶尔识别不了指纹，站在那儿按七八次很尴尬，能不能加个工牌刷卡。"),
    ("laozhou", "建议内网开个技术分享板块，最近组里几个人在做的东西互相都不知道。"),
    ("xiaolin", "早高峰电梯排队太久了，八点五十到楼下基本要等两轮，能不能错峰。"),
    ("amei", "想申请每周一天在家办公，出差多的活儿在家效率反而高一些。"),
    ("laozhou", "文档站的搜索基本没用，搜关键词搜不到，建议换成全文检索。"),
    ("xiaolin", "食堂三楼那个窗口能不能多给点米饭，每次都不够吃。"),
    ("amei", "建议把周报模板简化一下，现在要填的项目太多，实质内容反而写不进去。"),
    ("laozhou", "测试环境的数据库每周都被清一次，能不能保留一周的数据方便排查。"),
]


def seed_demo():
    """灌入演示数据。

    只在 MW_SEED_DEMO=1 且当前一条留言都没有时执行，不会覆盖真实数据。
    """
    ids = {}
    for name, pwd in DEMO_USERS:
        user = db.get_user_by_name(name)
        if user is None:
            db.create_user(name, auth.hash_password(pwd))
            user = db.get_user_by_name(name)
        ids[name] = user["id"]
    for name, text in DEMO_MESSAGES:
        db.add_message(ids[name], name, text)
    print(" * 演示模式：已灌入 %d 条示例留言" % len(DEMO_MESSAGES))



bootstrap()

if __name__ == "__main__":
    print(" * 运行地址： http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)

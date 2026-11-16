# -*- coding: utf-8 -*-
"""
自动化测试
==========
用 Flask 自带的 test_client 跑一遍主要流程，不需要真的启动服务器。

运行：
    python -m pytest -q        （装了 pytest 的话）
    python tests/selftest.py   （什么都没装也能跑）
"""
import os
import sys
import tempfile

# 让测试用独立的临时数据库，不碰开发用的 wall.db
TMP_DB = os.path.join(tempfile.gettempdir(), "mw_test_%d.db" % os.getpid())
if os.path.exists(TMP_DB):
    os.remove(TMP_DB)
os.environ["MW_DB_PATH"] = TMP_DB
os.environ["MW_SECRET_KEY"] = "test-secret"
os.environ["MW_ADMIN_USER"] = "admin"
os.environ["MW_ADMIN_PASSWORD"] = "admin123"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402

app = app_module.app
app.config["TESTING"] = True

passed = []
failed = []


def check(name, cond, extra=""):
    if cond:
        passed.append(name)
        print("  PASS  %s" % name)
    else:
        failed.append(name)
        print("  FAIL  %s  %s" % (name, extra))


def run():
    c = app.test_client()

    # 1. 首页未登录可访问
    r = c.get("/")
    check("首页可访问", r.status_code == 200)

    # 2. 未登录不能发布
    r = c.get("/post")
    check("未登录访问发布页会跳登录", r.status_code == 302 and "/login" in r.headers["Location"])

    # 3. 注册
    r = c.post("/register", data={"username": "tester", "password": "secret1", "confirm": "secret1"})
    check("注册成功跳登录页", r.status_code == 302 and "/login" in r.headers["Location"])

    # 4. 密码太短会被拒
    r = c.post("/register", data={"username": "shortpw", "password": "123", "confirm": "123"})
    check("密码太短被拒", r.status_code == 200 and "至少 6 位" in r.get_data(as_text=True))

    # 5. 重复用户名被拒
    r = c.post("/register", data={"username": "tester", "password": "secret1", "confirm": "secret1"})
    check("重复用户名被拒", "已经被注册" in r.get_data(as_text=True))

    # 6. 密码错误登录失败
    r = c.post("/login", data={"username": "tester", "password": "wrong"})
    check("密码错误登录失败", "账号或密码不对" in r.get_data(as_text=True))

    # 7. 正确登录
    r = c.post("/login", data={"username": "tester", "password": "secret1"}, follow_redirects=True)
    check("登录成功进首页", r.status_code == 200 and "欢迎回来" in r.get_data(as_text=True))

    # 8. 发布留言
    r = c.post("/post", data={"content": "测试留言一"}, follow_redirects=True)
    check("发布留言成功", r.status_code == 200 and "测试留言一" in r.get_data(as_text=True))

    # 9. 发布空内容被拒
    r = c.post("/post", data={"content": "   "}, follow_redirects=True)
    check("空留言被拒", "不能为空" in r.get_data(as_text=True))

    # 10. 搜索
    r = c.get("/?kw=测试留言一")
    check("搜索命中", "测试留言一" in r.get_data(as_text=True))

    # 11. 搜索不到
    r = c.get("/?kw=绝对不存在的关键词xyz")
    check("搜索无结果提示", "没有找到" in r.get_data(as_text=True))

    # 12. 普通用户进不了后台
    r = c.get("/admin")
    check("普通用户进不了后台", r.status_code == 302)

    # 13. 普通用户导不了 Excel
    r = c.get("/admin/export")
    check("普通用户导不了 Excel", r.status_code == 302)

    # 14. 登出
    r = c.get("/logout", follow_redirects=True)
    check("登出成功", "已经退出登录" in r.get_data(as_text=True))

    # 15. 管理员登录
    r = c.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    check("管理员登录成功", "admin" in r.get_data(as_text=True))

    # 16. 管理员能进后台
    r = c.get("/admin")
    check("管理员能进后台", r.status_code == 200 and "管理后台" in r.get_data(as_text=True))

    # 17. 管理员能导出 Excel
    r = c.get("/admin/export")
    is_xlsx = r.status_code == 200 and r.data[:2] == b"PK"
    check("导出 Excel 是合法 xlsx", is_xlsx, "mimetype=%s" % r.mimetype)

    # 18. 分页：造 15 条数据后应出现 2 页
    for i in range(15):
        c.post("/post", data={"content": "批量留言 %02d" % i})
    r = c.get("/")
    check("分页出现第 2 页", "下一页" in r.get_data(as_text=True))
    r = c.get("/?page=2")
    check("第 2 页可访问", r.status_code == 200)

    # 19. 404
    r = c.get("/this-page-does-not-exist")
    check("404 页面自定义", r.status_code == 404 and "404" in r.get_data(as_text=True))

    # 20. 密码是哈希存的
    import db as dbm
    row = dbm.get_user_by_name("tester")
    ph = row["password_hash"] if row else ""
    check(
        "密码不是明文存储",
        ph != "secret1" and ":" in ph and len(ph) > 40,
        "hash=%r" % ph[:24],
    )

    print("\n%d passed, %d failed" % (len(passed), len(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    code = run()
    try:
        os.remove(TMP_DB)
    except OSError:
        pass
    sys.exit(code)

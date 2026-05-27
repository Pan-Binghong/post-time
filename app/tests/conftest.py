"""测试环境变量预设。

pytest 在导入测试模块前先加载 conftest.py，所以这里设置的环境变量
能在所有 app.* 模块被 import 时生效，避免 os.environ["KEY"] 报 KeyError。
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("AUTH_USERNAME", "admin")
os.environ.setdefault("AUTH_PASSWORD", "admin")

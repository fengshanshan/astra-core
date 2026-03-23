"""
独立的数据库初始化脚本。
用法：
  本地：python scripts/init_db.py
  Render：在 build.sh 中由 INIT_DB=true 触发自动执行

功能：
  1. 用 SQLAlchemy create_all() 建表（含最新 schema，包括 stage 字段）
  2. 初始化 system_prompt 表（若为空则写入默认占位符）
"""

import sys
import os

# 确保项目根目录在 Python 路径中（本地直接运行时需要）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.db import engine, SessionLocal
from app.models import Base
from app.models import User, Conversation, Message, SystemPrompt  # noqa: F401 触发模型注册


def init():
    print(">>> 创建所有数据表...")
    Base.metadata.create_all(bind=engine)
    print("    数据表创建完成。")

    print(">>> 检查 system_prompt 初始数据...")
    db = SessionLocal()
    try:
        row = db.query(SystemPrompt).filter_by(id=1).first()
        if not row:
            db.add(SystemPrompt(id=1, content=""))
            db.commit()
            print("    system_prompt 已初始化（内容为空，请在后台填写）。")
        else:
            print("    system_prompt 已存在，跳过。")
    finally:
        db.close()

    print(">>> 数据库初始化完成 ✓")


if __name__ == "__main__":
    init()

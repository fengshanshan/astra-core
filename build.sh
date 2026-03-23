#!/bin/bash
set -e
pip install -r requirements.txt

# 仅当 INIT_DB=true 时才初始化数据库（建表 + 初始数据）
# 在 Render Dashboard → Environment 中设置 INIT_DB=true 触发，完成后改回 false
if [ "${INIT_DB}" = "true" ]; then
  echo ">>> INIT_DB=true 检测到，开始初始化数据库..."
  python scripts/init_db.py
fi

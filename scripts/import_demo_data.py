"""导入示例数据到 LifeVault 数据库"""
import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db import get_db_path, init_database, insert_messages
from app.models.message import UnifiedMessage


async def main():
    # 读取示例数据
    demo_file = Path(__file__).parent.parent / "sample_data" / "demo.json"
    print(f"读取示例数据: {demo_file}")

    with open(demo_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages_data = data.get("messages", [])
    print(f"找到 {len(messages_data)} 条消息")

    # 转换为 UnifiedMessage 对象
    messages = []
    for msg_data in messages_data:
        try:
            msg = UnifiedMessage(**msg_data)
            messages.append(msg)
        except Exception as e:
            print(f"跳过无效消息 {msg_data.get('id')}: {e}")

    print(f"成功解析 {len(messages)} 条消息")

    # 初始化数据库
    db_path = await get_db_path()
    print(f"数据库路径: {db_path}")
    await init_database(db_path)

    # 插入消息
    print("开始导入...")
    imported = await insert_messages(messages)
    print(f"成功导入 {imported} 条消息")


if __name__ == "__main__":
    asyncio.run(main())

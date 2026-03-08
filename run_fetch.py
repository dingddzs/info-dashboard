#!/usr/bin/env python3
"""运行数据抓取（单独脚本）"""

import asyncio
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from fetchers import fetch_all_sources, init_db
from config import SOURCES

async def main():
    print("初始化数据库...")
    init_db()

    print(f"\n开始抓取 {len(SOURCES)} 个信息源...")
    results = await fetch_all_sources(SOURCES)

    print("\n抓取结果:")
    for r in results:
        status = "成功" if r['success'] else "失败"
        new_items = r.get('new_items', 0)
        print(f"  {status}: {r['name']} ({r['platform']}) - {new_items} 条新内容")

    # 计算总数
    total_new = sum(r.get('new_items', 0) for r in results if r['success'])
    print(f"\n总计: {total_new} 条新内容")

if __name__ == '__main__':
    asyncio.run(main())

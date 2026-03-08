"""信息源配置文件"""
import json
from pathlib import Path

def load_sources():
    """从JSON文件加载信源配置"""
    sources_file = Path(__file__).parent / "sources.json"
    if sources_file.exists():
        with open(sources_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# 监控的信息源列表
SOURCES = load_sources() or [
    {
        "id": "bili_1",
        "platform": "bilibili",
        "name": "巫师财经",
        "uid": 472747194,
        "enabled": True
    },
    {
        "id": "bili_2",
        "platform": "bilibili",
        "name": "陈睿",
        "uid": 208259,
        "enabled": True
    },
    # 示例：微信公众号（需要特殊处理，先占位）
    # {
    #     "id": "wechat_1",
    #     "platform": "wechat",
    #     "name": "半佛仙人",
    #     "account": "banfoxiaoren",
    #     "enabled": False
    # },
    # 示例：知乎
    # {
    #     "id": "zhihu_1",
    #     "platform": "zhihu",
    #     "name": "张佳玮",
    #     "user_id": "zhang-jia-wei",
    #     "enabled": False
    # },
    # RSS博客
    {
        "id": "blog_1",
        "platform": "rss",
        "name": "阮一峰的网络日志",
        "url": "https://www.ruanyifeng.com/blog/atom.xml",
        "enabled": True
    }
]

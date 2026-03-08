"""配置管理模块 - 支持运行时修改"""

import json
from pathlib import Path
from threading import Lock

CONFIG_FILE = Path(__file__).parent / "sources.json"
config_lock = Lock()

# 默认配置
DEFAULT_SOURCES = [
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
    {
        "id": "blog_1",
        "platform": "rss",
        "name": "阮一峰的网络日志",
        "url": "https://www.ruanyifeng.com/blog/atom.xml",
        "enabled": True
    }
]


def init_config():
    """初始化配置文件"""
    if not CONFIG_FILE.exists():
        save_sources(DEFAULT_SOURCES)
        return DEFAULT_SOURCES
    return load_sources()


def load_sources():
    """加载配置"""
    with config_lock:
        if not CONFIG_FILE.exists():
            return DEFAULT_SOURCES.copy()
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置失败: {e}")
            return DEFAULT_SOURCES.copy()


def save_sources(sources):
    """保存配置"""
    with config_lock:
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(sources, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False


def add_source(source_data):
    """添加信息源"""
    sources = load_sources()

    # 生成唯一ID
    platform = source_data['platform']
    existing_ids = [s['id'] for s in sources if s['id'].startswith(f"{platform}_")]
    max_num = 0
    for sid in existing_ids:
        try:
            num = int(sid.split('_')[-1])
            max_num = max(max_num, num)
        except:
            pass

    new_id = f"{platform}_{max_num + 1}"

    # 构建新信源
    new_source = {
        "id": new_id,
        "platform": platform,
        "name": source_data['name'],
        "enabled": True
    }

    # 根据平台添加特定字段
    if platform == 'bilibili':
        new_source['uid'] = int(source_data['uid'])
    elif platform == 'rss':
        new_source['url'] = source_data['url']
    elif platform == 'wechat':
        new_source['account'] = source_data['account']
    elif platform == 'zhihu':
        new_source['user_id'] = source_data['user_id']

    sources.append(new_source)

    if save_sources(sources):
        return {"success": True, "source": new_source}
    else:
        return {"success": False, "error": "保存失败"}


def delete_source(source_id):
    """删除信息源"""
    sources = load_sources()
    sources = [s for s in sources if s['id'] != source_id]

    if save_sources(sources):
        return {"success": True}
    else:
        return {"success": False, "error": "保存失败"}


def toggle_source(source_id, enabled):
    """启用/禁用信息源"""
    sources = load_sources()
    for s in sources:
        if s['id'] == source_id:
            s['enabled'] = enabled
            break

    if save_sources(sources):
        return {"success": True}
    else:
        return {"success": False, "error": "保存失败"}


def validate_source(source_data):
    """验证信源数据"""
    platform = source_data.get('platform')
    name = source_data.get('name', '').strip()

    if not platform:
        return False, "请选择平台"
    if not name:
        return False, "请输入名称"

    if platform == 'bilibili':
        uid = source_data.get('uid', '').strip()
        if not uid or not uid.isdigit():
            return False, "请输入有效的UID（数字）"
        # 简化验证，只检查格式
        return True, "格式正确，添加后将自动验证"

    elif platform == 'rss':
        url = source_data.get('url', '').strip()
        if not url.startswith(('http://', 'https://')):
            return False, "请输入有效的URL（以http://或https://开头）"
        # 简化验证
        return True, "格式正确，添加后将自动验证"

    elif platform == 'wechat':
        account = source_data.get('account', '').strip()
        if not account:
            return False, "请输入公众号ID"
        return True, "验证成功"

    elif platform == 'zhihu':
        user_id = source_data.get('user_id', '').strip()
        if not user_id:
            return False, "请输入知乎用户ID"
        return True, "验证成功"

    return False, "不支持的平台"

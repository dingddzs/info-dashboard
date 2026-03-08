"""Vercel API Handler - 简化版"""

import json
import sys
from pathlib import Path

# 确保能导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))

def handler(request):
    """Vercel Python Handler"""
    from database import ContentStore, ContactStore, get_upcoming_reminders, init_db
    from config_manager import load_sources

    # 初始化数据库
    init_db()

    path = request.path
    method = request.method

    # 首页 - 返回dashboard.html
    if path == '/' or path == '/index.html':
        html_file = Path(__file__).parent.parent / 'dashboard.html'
        if html_file.exists():
            content = html_file.read_text(encoding='utf-8')
            return request.Response(
                content,
                status_code=200,
                headers={'Content-Type': 'text/html; charset=utf-8'}
            )

    # 主题CSS文件
    if path.startswith('/themes/'):
        theme_file = Path(__file__).parent.parent / path.lstrip('/')
        if theme_file.exists() and theme_file.suffix == '.css':
            content = theme_file.read_text(encoding='utf-8')
            return request.Response(
                content,
                status_code=200,
                headers={'Content-Type': 'text/css'}
            )

    # API路由
    if path == '/api/contacts':
        contacts = ContactStore().get_contacts()
        return request.Response(
            json.dumps({'contacts': contacts}),
            status_code=200,
            headers={'Content-Type': 'application/json'}
        )

    if path == '/api/reminders':
        reminders = get_upcoming_reminders()
        return request.Response(
            json.dumps(reminders),
            status_code=200,
            headers={'Content-Type': 'application/json'}
        )

    if path == '/api/stats':
        store = ContentStore()
        stats = store.get_source_stats()
        total = sum(s['total'] for s in stats.values())
        today = sum(s.get('today', 0) for s in stats.values())
        return request.Response(
            json.dumps({'sources': len(stats), 'total_updates': total, 'today_updates': today}),
            status_code=200,
            headers={'Content-Type': 'application/json'}
        )

    if path == '/api/updates':
        store = ContentStore()
        updates = store.get_today_updates()
        return request.Response(
            json.dumps({'updates': updates}),
            status_code=200,
            headers={'Content-Type': 'application/json'}
        )

    if path == '/api/sources':
        sources = load_sources()
        return request.Response(
            json.dumps({'sources': sources}),
            status_code=200,
            headers={'Content-Type': 'application/json'}
        )

    return request.Response('Not Found', status_code=404)

import json
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def handler(req, res):
    """Vercel Python Handler"""
    from database import ContentStore, ContactStore, get_upcoming_reminders, init_db
    from config_manager import load_sources

    # 初始化
    init_db()

    path = req.path

    # 首页
    if path == '/' or path == '/index.html':
        html_file = Path(__file__).parent.parent / 'dashboard.html'
        if html_file.exists():
            content = html_file.read_text(encoding='utf-8')
            return res.send(content, status=200, headers={'Content-Type': 'text/html'})

    # 主题CSS
    if path.startswith('/themes/'):
        theme_file = Path(__file__).parent.parent / path.lstrip('/')
        if theme_file.exists() and theme_file.suffix == '.css':
            content = theme_file.read_text(encoding='utf-8')
            return res.send(content, status=200, headers={'Content-Type': 'text/css'})

    # API
    if path == '/api/contacts':
        contacts = ContactStore().get_contacts()
        return res.json({'contacts': contacts})

    if path == '/api/reminders':
        reminders = get_upcoming_reminders()
        return res.json(reminders)

    if path == '/api/stats':
        store = ContentStore()
        stats = store.get_source_stats()
        total = sum(s['total'] for s in stats.values())
        today = sum(s.get('today', 0) for s in stats.values())
        return res.json({'sources': len(stats), 'total_updates': total, 'today_updates': today})

    if path == '/api/updates':
        store = ContentStore()
        updates = store.get_today_updates()
        return res.json({'updates': updates})

    if path == '/api/sources':
        sources = load_sources()
        return res.json({'sources': sources})

    return res.send('Not Found', status=404)

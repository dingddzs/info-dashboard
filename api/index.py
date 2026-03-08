"""Vercel Python Handler"""

def handler(request, context):
    """Vercel Python入口函数"""
    from database import ContentStore, ContactStore, get_upcoming_reminders, init_db
    from config_manager import load_sources
    import json
    from pathlib import Path
    import sys

    # 添加路径
    sys.path.insert(0, str(Path(__file__).parent.parent))

    # 初始化
    init_db()

    path = request.url.path
    method = request.method

    # 首页
    if path == '/' or path == '/index.html':
        html_file = Path(__file__).parent.parent / 'dashboard.html'
        if html_file.exists():
            content = html_file.read_text(encoding='utf-8')
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/html; charset=utf-8'},
                'body': content
            }
        return {'statusCode': 404, 'body': 'Not found'}

    # 主题CSS
    if path.startswith('/themes/'):
        theme_file = Path(__file__).parent.parent / path.lstrip('/')
        if theme_file.exists() and theme_file.suffix == '.css':
            content = theme_file.read_text(encoding='utf-8')
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/css'},
                'body': content
            }
        return {'statusCode': 404, 'body': 'Not found'}

    # API
    if path == '/api/contacts':
        contacts = ContactStore().get_contacts()
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'contacts': contacts})
        }

    if path == '/api/reminders':
        reminders = get_upcoming_reminders()
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(reminders)
        }

    if path == '/api/stats':
        store = ContentStore()
        stats = store.get_source_stats()
        total = sum(s['total'] for s in stats.values())
        today = sum(s.get('today', 0) for s in stats.values())
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'sources': len(stats), 'total_updates': total, 'today_updates': today})
        }

    if path == '/api/updates':
        store = ContentStore()
        updates = store.get_today_updates()
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'updates': updates})
        }

    if path == '/api/sources':
        sources = load_sources()
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'sources': sources})
        }

    return {'statusCode': 404, 'body': 'Not found'}

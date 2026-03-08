"""信息源监控看板 V4 - 综合仪表盘 + 人脉管理"""

import asyncio
import json
import urllib.parse
from datetime import datetime, date
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import webbrowser

from database import ContentStore, ContactStore, init_db, get_upcoming_reminders, ignore_reminder
from fetchers import fetch_all_sources
from config_manager import load_sources, add_source, delete_source, toggle_source, validate_source, init_config
from summarizer import batch_summarize


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP请求处理"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 页面路由
        if path == '/' or path == '/index.html':
            self.serve_dashboard()
        elif path == '/sources':
            self.serve_sources_page()
        elif path == '/contacts':
            self.serve_contacts_page()
        # 静态文件 - 主题CSS
        elif path.startswith('/themes/'):
            self.serve_theme(path)
        # API路由 - 信息源
        elif path == '/api/stats':
            self.serve_stats()
        elif path == '/api/updates':
            self.serve_updates()
        elif path == '/api/sources':
            self.serve_sources_api()
        elif path == '/api/source/detail':
            self.serve_source_detail_api(query)
        elif path == '/api/search':
            self.serve_search(query)
        # API路由 - 人脉管理
        elif path == '/api/reminders':
            self.serve_reminders()
        elif path == '/api/contacts':
            self.serve_contacts_api()
        elif path == '/api/contact/detail':
            self.serve_contact_detail_api(query)
        elif path == '/api/contact/todos':
            self.serve_contact_todos_api(query)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 信息源管理
        if path == '/api/sources/add':
            self.handle_add_source()
        elif path == '/api/sources/delete':
            self.handle_delete_source()
        elif path == '/api/sources/toggle':
            self.handle_toggle_source()
        elif path == '/api/sources/validate':
            self.handle_validate_source()
        elif path == '/api/refresh':
            self.handle_refresh()
        # 人脉管理
        elif path == '/api/contacts/add':
            self.handle_add_contact()
        elif path == '/api/contacts/update':
            self.handle_update_contact()
        elif path == '/api/contacts/delete':
            self.handle_delete_contact()
        elif path == '/api/todos/add':
            self.handle_add_todo()
        elif path == '/api/todos/toggle':
            self.handle_toggle_todo()
        elif path == '/api/todos/delete':
            self.handle_delete_todo()
        elif path == '/api/reminders/ignore':
            self.handle_ignore_reminder()
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass

    # ========== 页面服务 ==========

    def serve_dashboard(self):
        """综合仪表盘 - 从dashboard.html读取"""
        from pathlib import Path
        html_file = Path(__file__).parent / 'dashboard.html'
        if html_file.exists():
            html = html_file.read_text(encoding='utf-8')
            self.send_html(html)
        else:
            # 备用：使用内联HTML
            html = self.generate_dashboard_html()
            self.send_html(html)

    def serve_sources_page(self):
        """信源管理页"""
        html = self.generate_sources_html()
        self.send_html(html)

    def serve_contacts_page(self):
        """人脉管理页"""
        html = self.generate_contacts_html()
        self.send_html(html)

    # ========== API服务 - 信息源 ==========

    def serve_stats(self):
        """统计数据"""
        store = ContentStore()
        stats = store.get_source_stats()
        sources = load_sources()
        today_count = sum(s['today'] for s in stats.values())

        self.send_json({
            'sources': len([s for s in sources if s.get('enabled', True)]),
            'today_updates': today_count
        })

    def serve_updates(self):
        """今日更新"""
        store = ContentStore()
        updates = store.get_today_updates()
        sources = load_sources()

        for u in updates:
            src = next((s for s in sources if s['id'] == u['source_id']), None)
            u['source_name'] = src['name'] if src else u['source_id']

        updates = batch_summarize(updates)

        for u in updates:
            if u.get('id') and u.get('summary'):
                store.update_summary(u['id'], u['summary'])

        self.send_json({'updates': updates})

    def serve_sources_api(self):
        """信源列表"""
        sources = load_sources()
        stats = ContentStore().get_source_stats()

        result = []
        for s in sources:
            stat = stats.get(s['id'], {'total': 0, 'today': 0})
            result.append({
                'id': s['id'],
                'name': s['name'],
                'platform': s['platform'],
                'enabled': s.get('enabled', True),
                'total': stat['total'],
                'today': stat['today']
            })

        self.send_json({'sources': result})

    def serve_source_detail_api(self, query):
        """信源详情"""
        source_id = query.get('id', [''])[0]
        search = query.get('search', [''])[0]

        if not source_id:
            self.send_json({'error': '缺少source_id'})
            return

        store = ContentStore()
        sources = load_sources()
        src = next((s for s in sources if s['id'] == source_id), None)

        if not src:
            self.send_json({'error': '信源不存在'})
            return

        updates = store.get_updates_by_source(source_id, search_query=search)

        self.send_json({
            'source': {'id': src['id'], 'name': src['name'], 'platform': src['platform']},
            'updates': updates
        })

    def serve_search(self, query):
        """全局搜索"""
        q = query.get('q', [''])[0]
        if not q:
            self.send_json({'results': []})
            return

        store = ContentStore()
        sources = load_sources()
        results = store.search_all(q)

        for r in results:
            src = next((s for s in sources if s['id'] == r['source_id']), None)
            r['source_name'] = src['name'] if src else r['source_id']

        self.send_json({'results': results})

    # ========== API服务 - 人脉管理 ==========

    def serve_reminders(self):
        """获取近期提醒"""
        reminders = get_upcoming_reminders()
        self.send_json(reminders)

    def serve_contacts_api(self):
        """获取所有人脉"""
        contacts = ContactStore().get_contacts()
        self.send_json({'contacts': contacts})

    def serve_contact_detail_api(self, query):
        """获取人物详情"""
        contact_id = int(query.get('id', ['0'])[0])
        contact = ContactStore().get_contact(contact_id)

        if not contact:
            self.send_json({'error': '人物不存在'})
            return

        todos = ContactStore().get_todos_by_contact(contact_id)
        contact['todos'] = todos

        self.send_json({'contact': contact})

    def serve_contact_todos_api(self, query):
        """获取人物待办"""
        contact_id = int(query.get('id', ['0'])[0])
        todos = ContactStore().get_todos_by_contact(contact_id)
        self.send_json({'todos': todos})

    # ========== POST处理 - 信息源 ==========

    def handle_add_source(self):
        """添加信源"""
        data = self.read_json_body()
        result = add_source(data)
        self.send_json(result)

    def handle_delete_source(self):
        """删除信源"""
        data = self.read_json_body()
        result = delete_source(data['id'])
        self.send_json(result)

    def handle_toggle_source(self):
        """启用/禁用信源"""
        data = self.read_json_body()
        result = toggle_source(data['id'], data['enabled'])
        self.send_json(result)

    def handle_validate_source(self):
        """验证信源"""
        data = self.read_json_body()
        valid, message = validate_source(data)
        self.send_json({'valid': valid, 'message': message})

    def handle_refresh(self):
        """手动刷新"""
        try:
            sources = load_sources()
            enabled = [s for s in sources if s.get('enabled', True)]

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(fetch_all_sources(enabled))
            loop.close()

            self.send_json({'success': True, 'results': results})
        except Exception as e:
            self.send_json({'success': False, 'error': str(e)})

    # ========== POST处理 - 人脉管理 ==========

    def handle_add_contact(self):
        """添加人物"""
        data = self.read_json_body()
        store = ContactStore()

        contact_id = store.add_contact(
            name=data['name'],
            gender=data.get('gender'),
            birthday=data.get('birthday'),
            identity=data.get('identity'),
            important_info=data.get('important_info')
        )

        self.send_json({'success': True, 'contact_id': contact_id})

    def handle_update_contact(self):
        """更新人物"""
        data = self.read_json_body()
        store = ContactStore()

        success = store.update_contact(
            contact_id=data['id'],
            name=data.get('name'),
            gender=data.get('gender'),
            birthday=data.get('birthday'),
            identity=data.get('identity'),
            important_info=data.get('important_info')
        )

        self.send_json({'success': success})

    def handle_delete_contact(self):
        """删除人物"""
        data = self.read_json_body()
        ContactStore().delete_contact(data['id'])
        self.send_json({'success': True})

    def handle_add_todo(self):
        """添加待办"""
        data = self.read_json_body()
        store = ContactStore()

        todo_id = store.add_todo(
            contact_id=data['contact_id'],
            task_content=data['task_content'],
            due_date=data.get('due_date')
        )

        self.send_json({'success': True, 'todo_id': todo_id})

    def handle_toggle_todo(self):
        """切换待办状态"""
        data = self.read_json_body()
        ContactStore().toggle_todo(data['todo_id'], data['is_completed'])
        self.send_json({'success': True})

    def handle_delete_todo(self):
        """删除待办"""
        data = self.read_json_body()
        ContactStore().delete_todo(data['todo_id'])
        self.send_json({'success': True})

    def handle_ignore_reminder(self):
        """忽略提醒（打勾取消）"""
        data = self.read_json_body()
        reminder_type = data.get('type')  # 'birthday' or 'todo'
        contact_id = data.get('contact_id')
        todo_id = data.get('todo_id')
        year = data.get('year')

        ignore_reminder(reminder_type, contact_id=contact_id, todo_id=todo_id, year=year)
        self.send_json({'success': True})

    # ========== 静态文件服务 ==========

    def serve_theme(self, path):
        """返回主题CSS文件"""
        from pathlib import Path
        theme_file = Path(__file__).parent / path.lstrip('/')
        if theme_file.exists() and theme_file.suffix == '.css':
            content = theme_file.read_text(encoding='utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/css; charset=utf-8')
            self.send_header('Cache-Control', 'max-age=3600')
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        else:
            self.send_error(404)

    # ========== 辅助方法 ==========

    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode('utf-8'))

    def read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode('utf-8'))

    # ========== HTML生成 - 综合仪表盘 ==========

    def generate_dashboard_html(self):
        """生成综合仪表盘HTML - 双栏布局"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>综合仪表盘 - 信息源监控</title>
    <style>
        ''' + self.get_common_styles() + '''
        .nav {
            display: flex;
            gap: 24px;
            padding: 16px 24px;
            background: #1e293b;
            border-bottom: 1px solid #334155;
        }
        .nav a {
            color: #94a3b8;
            text-decoration: none;
            font-size: 14px;
        }
        .nav a.active {
            color: #60a5fa;
            font-weight: 500;
        }
        .dashboard-container {
            display: flex;
            min-height: calc(100vh - 60px);
        }
        .main-content {
            flex: 0 0 70%;
            padding: 24px;
            border-right: 1px solid #334155;
        }
        .sidebar {
            flex: 0 0 30%;
            padding: 24px;
            background: #0f172a;
        }
        .section-title {
            font-size: 16px;
            color: #f8fafc;
            margin-bottom: 16px;
            font-weight: 500;
        }
        .update-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            transition: border-color 0.2s;
        }
        .update-card:hover {
            border-color: #475569;
        }
        .update-title {
            font-size: 15px;
            color: #f8fafc;
            text-decoration: none;
            display: block;
            margin-bottom: 8px;
        }
        .update-title:hover {
            color: #60a5fa;
        }
        .update-meta {
            font-size: 12px;
            color: #64748b;
            margin-bottom: 8px;
        }
        .platform-badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            margin-right: 8px;
        }
        .platform-bilibili { background: #00a1d6; color: white; }
        .platform-rss { background: #f97316; color: white; }
        .summary {
            color: #94a3b8;
            font-size: 13px;
            line-height: 1.5;
            padding-top: 8px;
            border-top: 1px solid #334155;
        }
        .summary-label {
            color: #60a5fa;
            font-size: 11px;
            margin-bottom: 4px;
        }
        .empty-state {
            text-align: center;
            padding: 48px;
            color: #64748b;
        }
        /* 侧边栏提醒样式 */
        .reminder-section {
            margin-bottom: 24px;
        }
        .reminder-title {
            font-size: 14px;
            color: #94a3b8;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .reminder-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
        }
        .reminder-card.urgent {
            border-color: #ef4444;
            background: rgba(239, 68, 68, 0.1);
        }
        .reminder-card.warning {
            border-color: #f59e0b;
            background: rgba(245, 158, 11, 0.1);
        }
        .reminder-card.info {
            border-color: #10b981;
            background: rgba(16, 185, 129, 0.1);
        }
        .reminder-text {
            font-size: 13px;
            color: #f8fafc;
            margin-bottom: 4px;
        }
        .reminder-meta {
            font-size: 11px;
            color: #64748b;
        }
        .reminder-days {
            float: right;
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 4px;
        }
        .days-urgent { background: #ef4444; color: white; }
        .days-warning { background: #f59e0b; color: white; }
        .days-info { background: #10b981; color: white; }
        .refresh-btn {
            position: fixed;
            bottom: 24px;
            right: calc(30% + 24px);
            padding: 12px 20px;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            box-shadow: 0 4px 20px rgba(59, 130, 246, 0.3);
        }
        .loading {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 6px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/" class="active">仪表盘</a>
        <a href="/sources">信源管理</a>
        <a href="/contacts">人脉管理</a>
    </div>

    <div class="dashboard-container">
        <div class="main-content">
            <div class="section-title">今日更新</div>
            <div id="updateList">
                <div class="empty-state">加载中...</div>
            </div>
        </div>

        <div class="sidebar">
            <div class="reminder-section">
                <div class="reminder-title">近期提醒</div>
                <div id="reminderList">
                    <div class="empty-state">加载中...</div>
                </div>
            </div>
        </div>
    </div>

    <button class="refresh-btn" onclick="refreshData()" id="refreshBtn">刷新</button>

    <script>
        async function loadUpdates() {
            const res = await fetch('/api/updates');
            const data = await res.json();
            const listEl = document.getElementById('updateList');

            if (data.updates.length === 0) {
                listEl.innerHTML = '<div class="empty-state">今日暂无更新</div>';
                return;
            }

            listEl.innerHTML = data.updates.map(u => `
                <div class="update-card">
                    <a href="${u.url}" target="_blank" class="update-title">${u.title}</a>
                    <div class="update-meta">
                        <span class="platform-badge platform-${u.platform}">${u.platform}</span>
                        <span>${u.source_name}</span>
                        <span>${new Date(u.published_at).toLocaleTimeString('zh-CN', {hour:'2-digit', minute:'2-digit'})}</span>
                    </div>
                    ${u.summary ? `
                    <div class="summary">
                        <div class="summary-label">AI总结</div>
                        ${u.summary}
                    </div>
                    ` : ''}
                </div>
            `).join('');
        }

        async function loadReminders() {
            const res = await fetch('/api/reminders');
            const data = await res.json();
            const listEl = document.getElementById('reminderList');

            let html = '';

            // 生日提醒
            if (data.birthdays.length > 0) {
                html += '<div style="margin-bottom:16px;">';
                data.birthdays.forEach(b => {
                    const daysClass = b.days_until <= 3 ? 'days-urgent' : (b.days_until <= 7 ? 'days-warning' : 'days-info');
                    const cardClass = b.days_until <= 3 ? 'urgent' : (b.days_until <= 7 ? 'warning' : 'info');
                    html += `
                        <div class="reminder-card ${cardClass}" style="display:flex; align-items:center; justify-content:space-between;">
                            <div style="flex:1;">
                                <span class="reminder-days ${daysClass}">${b.days_until === 0 ? '今天' : b.days_until + '天后'}</span>
                                <div class="reminder-text">${b.name} 的生日</div>
                                <div class="reminder-meta">${b.birthday}</div>
                            </div>
                            <input type="checkbox" title="取消此提醒" onclick="ignoreReminder('birthday', ${b.contact_id}, null, ${b.ignore_year})" style="width:20px; height:20px; cursor:pointer;">
                        </div>
                    `;
                });
                html += '</div>';
            }

            // 待办提醒
            if (data.todos.length > 0) {
                data.todos.forEach(t => {
                    const daysClass = t.days_until <= 3 ? 'days-urgent' : (t.days_until <= 7 ? 'days-warning' : 'days-info');
                    const cardClass = t.days_until <= 3 ? 'urgent' : (t.days_until <= 7 ? 'warning' : 'info');
                    html += `
                        <div class="reminder-card ${cardClass}" style="display:flex; align-items:center; justify-content:space-between;">
                            <div style="flex:1;">
                                <span class="reminder-days ${daysClass}">${t.days_until === 0 ? '今天' : t.days_until + '天后'}</span>
                                <div class="reminder-text">${t.task_content}</div>
                                <div class="reminder-meta">${t.contact_name}</div>
                            </div>
                            <input type="checkbox" title="标记完成" onclick="ignoreReminder('todo', ${t.contact_id}, ${t.todo_id}, null)" style="width:20px; height:20px; cursor:pointer;">
                        </div>
                    `;
                });
            }

            if (data.birthdays.length === 0 && data.todos.length === 0) {
                html = '<div class="empty-state" style="padding:24px;">未来10天内无提醒</div>';
            }

            listEl.innerHTML = html;
        }

        async function ignoreReminder(type, contactId, todoId, year) {
            await fetch('/api/reminders/ignore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: type,
                    contact_id: contactId,
                    todo_id: todoId,
                    year: year
                })
            });
            // 刷新提醒列表
            loadReminders();
        }

        async function refreshData() {
            const btn = document.getElementById('refreshBtn');
            btn.innerHTML = '<span class="loading"></span>抓取中...';
            btn.disabled = true;

            try {
                const res = await fetch('/api/refresh', { method: 'POST' });
                const data = await res.json();

                if (data.success) {
                    await loadUpdates();
                    alert('刷新成功！');
                } else {
                    alert('刷新失败: ' + data.error);
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            } finally {
                btn.innerHTML = '刷新';
                btn.disabled = false;
            }
        }

        // 初始化
        loadUpdates();
        loadReminders();
        setInterval(loadReminders, 60000); // 每分钟刷新提醒
    </script>
</body>
</html>'''

    # ========== HTML生成 - 信源管理 ==========

    def generate_sources_html(self):
        """生成信源管理页HTML"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>信源管理 - 信息源监控</title>
    <style>
        ''' + self.get_common_styles() + '''
        .nav {
            display: flex;
            gap: 24px;
            padding: 16px 24px;
            background: #1e293b;
            border-bottom: 1px solid #334155;
        }
        .nav a {
            color: #94a3b8;
            text-decoration: none;
            font-size: 14px;
        }
        .nav a.active {
            color: #60a5fa;
            font-weight: 500;
        }
        .content {
            padding: 24px;
            max-width: 900px;
        }
        .header-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }
        .search-box {
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }
        .search-box input {
            flex: 1;
            padding: 10px 16px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            color: #f8fafc;
        }
        .source-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .source-item {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            overflow: hidden;
        }
        .source-header {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 16px 20px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .source-header:hover {
            background: #252f47;
        }
        .source-icon {
            width: 44px;
            height: 44px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            font-weight: bold;
            color: white;
        }
        .source-bilibili { background: #00a1d6; }
        .source-rss { background: #f97316; }
        .source-wechat { background: #07c160; }
        .source-zhihu { background: #0066ff; }
        .source-info {
            flex: 1;
        }
        .source-name {
            font-size: 16px;
            color: #f8fafc;
            font-weight: 500;
            margin-bottom: 4px;
        }
        .source-meta {
            font-size: 13px;
            color: #64748b;
        }
        .source-stats {
            display: flex;
            gap: 16px;
            text-align: center;
        }
        .source-stat {
            padding: 0 12px;
        }
        .source-stat-value {
            font-size: 20px;
            font-weight: bold;
            color: #f8fafc;
        }
        .source-stat-label {
            font-size: 11px;
            color: #64748b;
            margin-top: 2px;
        }
        .expand-icon {
            color: #64748b;
            font-size: 18px;
            transition: transform 0.2s;
            padding: 8px;
        }
        .expand-icon.expanded {
            transform: rotate(180deg);
        }
        .source-actions {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .source-history {
            display: none;
            border-top: 1px solid #334155;
            background: #0f172a;
            max-height: 400px;
            overflow-y: auto;
        }
        .source-history.active {
            display: block;
        }
        .history-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 20px;
            border-bottom: 1px solid #1e293b;
        }
        .history-title {
            flex: 1;
            color: #e2e8f0;
            text-decoration: none;
            font-size: 14px;
        }
        .history-title:hover {
            color: #60a5fa;
        }
        .history-date {
            color: #64748b;
            font-size: 12px;
            white-space: nowrap;
        }
        .history-empty {
            padding: 32px;
            text-align: center;
            color: #64748b;
        }
        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 13px;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.9; }
        .btn-primary {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
        }
        .btn-danger {
            background: #ef4444;
            color: white;
        }
        .btn-secondary {
            background: #334155;
            color: #f8fafc;
        }
        .toggle-switch {
            width: 40px;
            height: 22px;
            background: #334155;
            border-radius: 11px;
            position: relative;
            cursor: pointer;
            transition: background 0.2s;
        }
        .toggle-switch.active {
            background: #10b981;
        }
        .toggle-switch::after {
            content: '';
            position: absolute;
            width: 18px;
            height: 18px;
            background: white;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: transform 0.2s;
        }
        .toggle-switch.active::after {
            transform: translateX(18px);
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            width: 90%;
            max-width: 450px;
            border: 1px solid #334155;
        }
        .modal-header {
            font-size: 18px;
            margin-bottom: 20px;
            color: #f8fafc;
        }
        .form-group {
            margin-bottom: 16px;
        }
        .form-group label {
            display: block;
            margin-bottom: 6px;
            font-size: 13px;
            color: #94a3b8;
        }
        .form-group input,
        .form-group select {
            width: 100%;
            padding: 10px 12px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 6px;
            color: #f8fafc;
            font-size: 14px;
        }
        .form-actions {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
            margin-top: 20px;
        }
        .validation-msg {
            padding: 10px;
            border-radius: 6px;
            margin-top: 12px;
            font-size: 13px;
            display: none;
        }
        .validation-msg.success {
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
        }
        .validation-msg.error {
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
        }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">仪表盘</a>
        <a href="/sources" class="active">信源管理</a>
        <a href="/contacts">人脉管理</a>
    </div>

    <div class="content">
        <div class="header-actions">
            <h2 style="color: #f8fafc;">我的信源</h2>
            <button class="btn btn-primary" onclick="showAddModal()">+ 添加信源</button>
        </div>

        <div class="search-box">
            <input type="text" id="globalSearch" placeholder="搜索所有历史更新...">
            <button class="btn btn-secondary" onclick="doGlobalSearch()">搜索</button>
        </div>

        <div class="source-list" id="sourceList">
            <div style="color: #64748b; text-align: center; padding: 48px;">加载中...</div>
        </div>
    </div>

    <!-- 添加信源弹窗 -->
    <div class="modal" id="addModal">
        <div class="modal-content">
            <div class="modal-header">添加信息源</div>
            <div class="form-group">
                <label>平台</label>
                <select id="platformSelect" onchange="onPlatformChange()">
                    <option value="">请选择</option>
                    <option value="bilibili">Bilibili</option>
                    <option value="rss">RSS/博客</option>
                </select>
            </div>
            <div class="form-group">
                <label>名称</label>
                <input type="text" id="sourceName" placeholder="给这个信源起个名字">
            </div>
            <div class="form-group" id="uidGroup" style="display:none;">
                <label>UID</label>
                <input type="text" id="sourceUid" placeholder="B站用户UID">
            </div>
            <div class="form-group" id="urlGroup" style="display:none;">
                <label>RSS地址</label>
                <input type="text" id="sourceUrl" placeholder="https://...">
            </div>
            <div class="validation-msg" id="validationMsg"></div>
            <div class="form-actions">
                <button class="btn btn-secondary" onclick="hideAddModal()">取消</button>
                <button class="btn btn-primary" onclick="addSource()">添加</button>
            </div>
        </div>
    </div>

    <!-- 搜索结果弹窗 -->
    <div class="modal" id="searchModal">
        <div class="modal-content" style="max-width: 700px; max-height: 80vh; overflow-y: auto;">
            <div class="modal-header">搜索结果</div>
            <div id="searchResults"></div>
            <div class="form-actions">
                <button class="btn btn-secondary" onclick="hideSearchModal()">关闭</button>
            </div>
        </div>
    </div>

    <script>
        const platformIcons = {
            bilibili: 'B',
            rss: 'R',
            wechat: 'W',
            zhihu: 'Z'
        };

        const historyCache = {};

        async function loadSources() {
            const res = await fetch('/api/sources');
            const data = await res.json();
            const listEl = document.getElementById('sourceList');

            if (data.sources.length === 0) {
                listEl.innerHTML = '<div style="color: #64748b; text-align: center; padding: 48px;">暂无信源</div>';
                return;
            }

            listEl.innerHTML = data.sources.map(s => `
                <div class="source-item" id="source-${s.id}">
                    <div class="source-header" onclick="toggleExpand('${s.id}')">
                        <div class="source-icon source-${s.platform}">${platformIcons[s.platform] || '?'}</div>
                        <div class="source-info">
                            <div class="source-name">${s.name}</div>
                            <div class="source-meta">${s.platform} · ${s.enabled ? '监控中' : '已暂停'}</div>
                        </div>
                        <div class="source-stats">
                            <div class="source-stat">
                                <div class="source-stat-value">${s.today}</div>
                                <div class="source-stat-label">今日</div>
                            </div>
                            <div class="source-stat">
                                <div class="source-stat-value">${s.total}</div>
                                <div class="source-stat-label">总计</div>
                            </div>
                        </div>
                        <div class="expand-icon" id="expand-${s.id}">▼</div>
                        <div class="source-actions" onclick="event.stopPropagation()">
                            <div class="toggle-switch ${s.enabled ? 'active' : ''}" onclick="toggleSource('${s.id}', ${!s.enabled})"></div>
                            <button class="btn btn-danger" onclick="deleteSource('${s.id}')">删除</button>
                        </div>
                    </div>
                    <div class="source-history" id="history-${s.id}">
                        <div class="history-loading">点击展开加载历史...</div>
                    </div>
                </div>
            `).join('');
        }

        async function toggleExpand(sourceId) {
            const historyEl = document.getElementById('history-' + sourceId);
            const expandIcon = document.getElementById('expand-' + sourceId);

            if (historyEl.classList.contains('active')) {
                historyEl.classList.remove('active');
                expandIcon.classList.remove('expanded');
            } else {
                historyEl.classList.add('active');
                expandIcon.classList.add('expanded');

                if (!historyCache[sourceId]) {
                    await loadHistory(sourceId);
                }
            }
        }

        async function loadHistory(sourceId) {
            const historyEl = document.getElementById('history-' + sourceId);
            historyEl.innerHTML = '<div class="history-loading">加载中...</div>';

            try {
                const res = await fetch('/api/source/detail?id=' + sourceId);
                const data = await res.json();

                historyCache[sourceId] = data.updates;

                if (data.updates.length === 0) {
                    historyEl.innerHTML = '<div class="history-empty">暂无信息</div>';
                } else {
                    historyEl.innerHTML = data.updates.slice(0, 20).map(u => `
                        <div class="history-item">
                            <a href="${u.url}" target="_blank" class="history-title">${u.title}</a>
                            <span class="history-date">${new Date(u.published_at).toLocaleDateString()}</span>
                        </div>
                    `).join('');
                }
            } catch (e) {
                historyEl.innerHTML = '<div class="history-empty">加载失败</div>';
            }
        }

        function showAddModal() {
            document.getElementById('addModal').classList.add('active');
            resetForm();
        }

        function hideAddModal() {
            document.getElementById('addModal').classList.remove('active');
        }

        function resetForm() {
            document.getElementById('platformSelect').value = '';
            document.getElementById('sourceName').value = '';
            document.getElementById('sourceUid').value = '';
            document.getElementById('sourceUrl').value = '';
            document.getElementById('uidGroup').style.display = 'none';
            document.getElementById('urlGroup').style.display = 'none';
            hideValidation();
        }

        function onPlatformChange() {
            const platform = document.getElementById('platformSelect').value;
            document.getElementById('uidGroup').style.display = platform === 'bilibili' ? 'block' : 'none';
            document.getElementById('urlGroup').style.display = platform === 'rss' ? 'block' : 'none';
        }

        function showValidation(success, msg) {
            const el = document.getElementById('validationMsg');
            el.textContent = msg;
            el.className = 'validation-msg ' + (success ? 'success' : 'error');
            el.style.display = 'block';
        }

        function hideValidation() {
            document.getElementById('validationMsg').style.display = 'none';
        }

        async function addSource() {
            const platform = document.getElementById('platformSelect').value;
            const name = document.getElementById('sourceName').value.trim();

            if (!platform || !name) {
                showValidation(false, '请填写完整信息');
                return;
            }

            const data = { platform, name };
            if (platform === 'bilibili') {
                data.uid = document.getElementById('sourceUid').value.trim();
            } else if (platform === 'rss') {
                data.url = document.getElementById('sourceUrl').value.trim();
            }

            const valRes = await fetch('/api/sources/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const valData = await valRes.json();

            if (!valData.valid) {
                showValidation(false, valData.message);
                return;
            }

            const addRes = await fetch('/api/sources/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const addData = await addRes.json();

            if (addData.success) {
                hideAddModal();
                loadSources();
            } else {
                showValidation(false, addData.error);
            }
        }

        async function deleteSource(id) {
            if (!confirm('确定删除？')) return;
            await fetch('/api/sources/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id })
            });
            delete historyCache[id];
            loadSources();
        }

        async function toggleSource(id, enabled) {
            await fetch('/api/sources/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id, enabled })
            });
            loadSources();
        }

        async function doGlobalSearch() {
            const q = document.getElementById('globalSearch').value.trim();
            if (!q) return;

            const res = await fetch('/api/search?q=' + encodeURIComponent(q));
            const data = await res.json();

            const resultsEl = document.getElementById('searchResults');
            if (data.results.length === 0) {
                resultsEl.innerHTML = '<div style="color: #64748b; text-align: center; padding: 32px;">无结果</div>';
            } else {
                resultsEl.innerHTML = data.results.map(r => `
                    <div style="padding: 12px; border-bottom: 1px solid #334155;">
                        <a href="${r.url}" target="_blank" style="color: #60a5fa; text-decoration: none;">${r.title}</a>
                        <div style="color: #64748b; font-size: 12px; margin-top: 4px;">
                            ${r.source_name} · ${new Date(r.published_at).toLocaleDateString()}
                        </div>
                    </div>
                `).join('');
            }
            document.getElementById('searchModal').classList.add('active');
        }

        function hideSearchModal() {
            document.getElementById('searchModal').classList.remove('active');
        }

        loadSources();
    </script>
</body>
</html>'''

    # ========== HTML生成 - 人脉管理 ==========

    def generate_contacts_html(self):
        """生成人脉管理页HTML"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>人脉管理 - 信息源监控</title>
    <style>
        ''' + self.get_common_styles() + '''
        .nav {
            display: flex;
            gap: 24px;
            padding: 16px 24px;
            background: #1e293b;
            border-bottom: 1px solid #334155;
        }
        .nav a {
            color: #94a3b8;
            text-decoration: none;
            font-size: 14px;
        }
        .nav a.active {
            color: #60a5fa;
            font-weight: 500;
        }
        .content {
            padding: 24px;
            max-width: 1000px;
        }
        .header-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }
        .contact-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
        }
        .contact-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .contact-card:hover {
            border-color: #475569;
        }
        .contact-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        .contact-avatar {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            font-weight: bold;
            color: white;
        }
        .contact-info h3 {
            color: #f8fafc;
            font-size: 16px;
            margin-bottom: 4px;
        }
        .contact-info .identity {
            color: #64748b;
            font-size: 13px;
        }
        .contact-meta {
            font-size: 12px;
            color: #94a3b8;
            margin-top: 8px;
        }
        .contact-todo-count {
            float: right;
            background: #334155;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
        }
        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 13px;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.9; }
        .btn-primary {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
        }
        .btn-danger {
            background: #ef4444;
            color: white;
        }
        .btn-secondary {
            background: #334155;
            color: #f8fafc;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            width: 90%;
            max-width: 500px;
            max-height: 80vh;
            overflow-y: auto;
            border: 1px solid #334155;
        }
        .modal-header {
            font-size: 18px;
            margin-bottom: 20px;
            color: #f8fafc;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .form-group {
            margin-bottom: 16px;
        }
        .form-group label {
            display: block;
            margin-bottom: 6px;
            font-size: 13px;
            color: #94a3b8;
        }
        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 10px 12px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 6px;
            color: #f8fafc;
            font-size: 14px;
        }
        .form-group textarea {
            min-height: 80px;
            resize: vertical;
        }
        .form-actions {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
            margin-top: 20px;
        }
        .detail-section {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #334155;
        }
        .detail-section:last-child {
            border-bottom: none;
        }
        .detail-label {
            font-size: 12px;
            color: #94a3b8;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .detail-content {
            color: #f8fafc;
            font-size: 14px;
            line-height: 1.5;
        }
        .todo-list {
            margin-top: 12px;
        }
        .todo-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px;
            background: #0f172a;
            border-radius: 6px;
            margin-bottom: 8px;
        }
        .todo-checkbox {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        .todo-text {
            flex: 1;
            font-size: 13px;
            color: #e2e8f0;
        }
        .todo-text.completed {
            text-decoration: line-through;
            color: #64748b;
        }
        .todo-date {
            font-size: 11px;
            color: #64748b;
        }
        .todo-delete {
            color: #ef4444;
            cursor: pointer;
            font-size: 16px;
            padding: 0 4px;
        }
        .add-todo-form {
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }
        .add-todo-form input {
            flex: 1;
            padding: 8px 12px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 6px;
            color: #f8fafc;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">仪表盘</a>
        <a href="/sources">信源管理</a>
        <a href="/contacts" class="active">人脉管理</a>
    </div>

    <div class="content">
        <div class="header-actions">
            <h2 style="color: #f8fafc;">我的人才库</h2>
            <button class="btn btn-primary" onclick="showAddModal()">+ 添加人物</button>
        </div>

        <div class="contact-grid" id="contactList">
            <div style="color: #64748b; text-align: center; padding: 48px;">加载中...</div>
        </div>
    </div>

    <!-- 添加人物弹窗 -->
    <div class="modal" id="addModal">
        <div class="modal-content">
            <div class="modal-header">
                <span>添加人物</span>
                <span style="cursor: pointer;" onclick="hideAddModal()">✕</span>
            </div>
            <div class="form-group">
                <label>姓名 *</label>
                <input type="text" id="contactName" placeholder="姓名">
            </div>
            <div class="form-group">
                <label>性别</label>
                <select id="contactGender" style="width: 100%; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px;">
                    <option value="">未设置</option>
                    <option value="男">男</option>
                    <option value="女">女</option>
                    <option value="其他">其他</option>
                </select>
            </div>
            <div class="form-group">
                <label>生日</label>
                <input type="date" id="contactBirthday">
            </div>
            <div class="form-group">
                <label>身份/职业</label>
                <input type="text" id="contactIdentity" placeholder="如：产品经理、投资人...">
            </div>
            <div class="form-group">
                <label>重要备忘</label>
                <textarea id="contactInfo" placeholder="记录重要信息、偏好、合作历史等..."></textarea>
            </div>
            <div class="form-actions">
                <button class="btn btn-secondary" onclick="hideAddModal()">取消</button>
                <button class="btn btn-primary" onclick="addContact()">添加</button>
            </div>
        </div>
    </div>

    <!-- 人物详情弹窗 -->
    <div class="modal" id="detailModal">
        <div class="modal-content" id="detailContent">
            <!-- 动态生成 -->
        </div>
    </div>

    <script>
        async function loadContacts() {
            const res = await fetch('/api/contacts');
            const data = await res.json();
            const listEl = document.getElementById('contactList');

            if (data.contacts.length === 0) {
                listEl.innerHTML = '<div style="color: #64748b; text-align: center; padding: 48px;">暂无人物</div>';
                return;
            }

            listEl.innerHTML = data.contacts.map(c => `
                <div class="contact-card" onclick="showDetail(${c.id})">
                    <div class="contact-header">
                        <div class="contact-avatar">${c.name.charAt(0)}</div>
                        <div class="contact-info" style="flex: 1;">
                            <h3>${c.name} ${c.gender ? '<span style="font-size:12px; color:#64748b;">(' + c.gender + ')</span>' : ''}</h3>
                            <div class="identity">${c.identity || '无身份标签'}</div>
                        </div>
                    </div>
                    ${c.birthday ? `<div class="contact-meta">生日: ${c.birthday}</div>` : ''}
                </div>
            `).join('');
        }

        function showAddModal() {
            document.getElementById('addModal').classList.add('active');
            document.getElementById('contactName').value = '';
            document.getElementById('contactGender').value = '';
            document.getElementById('contactBirthday').value = '';
            document.getElementById('contactIdentity').value = '';
            document.getElementById('contactInfo').value = '';
        }

        function hideAddModal() {
            document.getElementById('addModal').classList.remove('active');
        }

        async function addContact() {
            const name = document.getElementById('contactName').value.trim();
            if (!name) {
                alert('请输入姓名');
                return;
            }

            const genderSelect = document.getElementById('contactGender');
            const data = {
                name: name,
                gender: genderSelect.value,
                birthday: document.getElementById('contactBirthday').value,
                identity: document.getElementById('contactIdentity').value.trim(),
                important_info: document.getElementById('contactInfo').value.trim()
            };

            await fetch('/api/contacts/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            hideAddModal();
            loadContacts();
        }

        async function showDetail(contactId) {
            const res = await fetch('/api/contact/detail?id=' + contactId);
            const data = await res.json();

            if (data.error) {
                alert(data.error);
                return;
            }

            const c = data.contact;
            const contentEl = document.getElementById('detailContent');

            contentEl.innerHTML = `
                <div class="modal-header">
                    <span>${c.name}</span>
                    <div>
                        <button class="btn btn-danger" onclick="deleteContact(${c.id})" style="margin-right: 8px;">删除</button>
                        <span style="cursor: pointer;" onclick="hideDetailModal()">✕</span>
                    </div>
                </div>

                <div class="detail-section">
                    <div class="detail-label">基本信息</div>
                    <div class="detail-content">
                        ${c.gender ? `<p>性别: ${c.gender}</p>` : ''}
                        ${c.identity ? `<p>身份: ${c.identity}</p>` : ''}
                        ${c.birthday ? `<p>生日: ${c.birthday}</p>` : '<p>生日: 未设置</p>'}
                    </div>
                </div>

                <div class="detail-section">
                    <div class="detail-label">重要备忘</div>
                    <div class="detail-content">${c.important_info || '无备忘信息'}</div>
                </div>

                <div class="detail-section">
                    <div class="detail-label">待办事项</div>
                    <div class="todo-list" id="todoList">
                        ${c.todos.length === 0 ? '<div style="color: #64748b; font-size: 13px;">暂无待办</div>' : c.todos.map(t => `
                            <div class="todo-item">
                                <input type="checkbox" class="todo-checkbox" ${t.is_completed ? 'checked' : ''} onchange="toggleTodo(${t.id}, this.checked)">
                                <span class="todo-text ${t.is_completed ? 'completed' : ''}">${t.task_content}</span>
                                ${t.due_date ? `<span class="todo-date">${t.due_date}</span>` : ''}
                                <span class="todo-delete" onclick="deleteTodo(${t.id})">✕</span>
                            </div>
                        `).join('')}
                    </div>
                    <div class="add-todo-form">
                        <input type="text" id="newTodoText" placeholder="添加新待办...">
                        <input type="date" id="newTodoDate" style="width: 130px;">
                        <button class="btn btn-primary" onclick="addTodo(${c.id})">添加</button>
                    </div>
                </div>
            `;

            document.getElementById('detailModal').classList.add('active');
        }

        function hideDetailModal() {
            document.getElementById('detailModal').classList.remove('active');
        }

        async function deleteContact(id) {
            if (!confirm('确定删除该人物？相关待办也会被删除。')) return;

            await fetch('/api/contacts/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id })
            });

            hideDetailModal();
            loadContacts();
        }

        async function addTodo(contactId) {
            const text = document.getElementById('newTodoText').value.trim();
            const dueDate = document.getElementById('newTodoDate').value;

            if (!text) return;

            await fetch('/api/todos/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contact_id: contactId,
                    task_content: text,
                    due_date: dueDate
                })
            });

            showDetail(contactId);
        }

        async function toggleTodo(todoId, isCompleted) {
            await fetch('/api/todos/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ todo_id: todoId, is_completed: isCompleted })
            });
        }

        async function deleteTodo(todoId) {
            if (!confirm('确定删除？')) return;

            await fetch('/api/todos/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ todo_id: todoId })
            });

            // 刷新详情弹窗
            const contactId = document.querySelector('.modal-header').innerHTML.match(/onclick="deleteContact\((\d+)\)/)?.[1];
            if (contactId) showDetail(parseInt(contactId));
        }

        loadContacts();
    </script>
</body>
</html>'''

    def get_common_styles(self):
        """公共CSS样式"""
        return '''
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        '''


def get_local_ip():
    """获取本机局域网IP"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def start_server(port=8080, host='0.0.0.0'):
    """启动服务器"""
    init_db()
    init_config()

    local_ip = get_local_ip()
    server = HTTPServer((host, port), DashboardHandler)
    print(f"\n{'='*50}")
    print(f"  信息源监控看板 已启动!")
    print(f"{'='*50}")
    print(f"  电脑访问: http://localhost:{port}")
    print(f"  手机访问: http://{local_ip}:{port}")
    print(f"{'='*50}")
    print("  按 Ctrl+C 停止服务\n")

    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{port}')).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()


if __name__ == '__main__':
    print("正在初始化...")
    init_db()
    init_config()

    sources = load_sources()
    enabled = [s for s in sources if s.get('enabled', True)]

    if enabled:
        print(f"抓取 {len(enabled)} 个信源的初始数据...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(fetch_all_sources(enabled))
        loop.close()

    start_server()

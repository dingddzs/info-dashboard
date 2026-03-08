"""信息源监控看板 V2 - 支持交互式信源管理"""

import asyncio
import json
from datetime import datetime, date
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import webbrowser

from fetchers import ContentStore, fetch_all_sources, init_db
from config_manager import load_sources, add_source, delete_source, toggle_source, validate_source, init_config


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP请求处理"""

    def do_GET(self):
        path = self.path

        if path == '/':
            self.serve_html()
        elif path == '/api/stats':
            self.serve_stats()
        elif path == '/api/updates':
            self.serve_updates()
        elif path == '/api/sources':
            self.serve_sources()
        elif path == '/api/history':
            self.serve_history()
        elif path == '/api/refresh':
            self.handle_refresh()
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path

        if path == '/api/sources/add':
            self.handle_add_source()
        elif path == '/api/sources/delete':
            self.handle_delete_source()
        elif path == '/api/sources/toggle':
            self.handle_toggle_source()
        elif path == '/api/sources/validate':
            self.handle_validate_source()
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """简化日志"""
        pass

    def serve_html(self):
        """返回主页HTML"""
        html = Path(__file__).parent / "dashboard_v2.html"
        if html.exists():
            content = html.read_text(encoding='utf-8')
        else:
            content = self.generate_html()

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def serve_stats(self):
        """返回统计数据"""
        store = ContentStore()
        stats = store.get_source_stats()
        sources = load_sources()
        today_count = sum(s['today'] for s in stats.values())
        total_count = sum(s['total'] for s in stats.values())

        self.send_json({
            'sources': len([s for s in sources if s.get('enabled', True)]),
            'total_sources': len(sources),
            'today_updates': today_count,
            'total_updates': total_count,
            'source_stats': stats
        })

    def serve_updates(self):
        """返回今日更新"""
        store = ContentStore()
        updates = store.get_today_updates()
        sources = load_sources()

        # 添加信息源名称
        for u in updates:
            src = next((s for s in sources if s['id'] == u['source_id']), None)
            u['source_name'] = src['name'] if src else u['source_id']

        self.send_json({'updates': updates})

    def serve_sources(self):
        """返回信息源列表"""
        sources = load_sources()
        self.send_json({
            'sources': [
                {
                    'id': s['id'],
                    'name': s['name'],
                    'platform': s['platform'],
                    'enabled': s.get('enabled', True),
                    'uid': s.get('uid'),
                    'url': s.get('url'),
                    'account': s.get('account'),
                    'user_id': s.get('user_id')
                }
                for s in sources
            ]
        })

    def serve_history(self):
        """返回历史数据"""
        store = ContentStore()
        history = store.get_recent_updates(30)
        self.send_json({'history': history})

    def handle_refresh(self):
        """手动刷新"""
        try:
            sources = load_sources()
            enabled_sources = [s for s in sources if s.get('enabled', True)]

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(fetch_all_sources(enabled_sources))
            loop.close()

            self.send_json({
                'success': True,
                'results': results
            })
        except Exception as e:
            self.send_json({
                'success': False,
                'error': str(e)
            })

    def handle_add_source(self):
        """添加信息源"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            result = add_source(data)
            self.send_json(result)
        except Exception as e:
            self.send_json({'success': False, 'error': str(e)})

    def handle_delete_source(self):
        """删除信息源"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            result = delete_source(data['id'])
            self.send_json(result)
        except Exception as e:
            self.send_json({'success': False, 'error': str(e)})

    def handle_toggle_source(self):
        """启用/禁用信息源"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            result = toggle_source(data['id'], data['enabled'])
            self.send_json(result)
        except Exception as e:
            self.send_json({'success': False, 'error': str(e)})

    def handle_validate_source(self):
        """验证信息源"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            valid, message = validate_source(data)
            self.send_json({'valid': valid, 'message': message})
        except Exception as e:
            self.send_json({'valid': False, 'message': str(e)})

    def send_json(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def generate_html(self):
        """生成HTML页面"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>信息源监控看板</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 24px;
            border-bottom: 1px solid #334155;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 24px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header .date {
            color: #94a3b8;
            font-size: 14px;
            margin-top: 4px;
        }
        .header-actions {
            display: flex;
            gap: 12px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            padding: 24px;
        }
        .stat-card {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #334155;
        }
        .stat-card .label {
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 8px;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
            color: #f8fafc;
        }
        .stat-card .value.today {
            color: #34d399;
        }
        .content {
            padding: 24px;
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 24px;
        }
        @media (max-width: 1024px) {
            .content { grid-template-columns: 1fr; }
        }
        .section {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #334155;
        }
        .section-title {
            font-size: 18px;
            margin-bottom: 16px;
            color: #f8fafc;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-title::before {
            content: '';
            width: 4px;
            height: 20px;
            background: linear-gradient(180deg, #60a5fa, #a78bfa);
            border-radius: 2px;
        }
        .update-list {
            max-height: 400px;
            overflow-y: auto;
        }
        .update-item {
            padding: 12px;
            border-bottom: 1px solid #334155;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }
        .update-item:last-child {
            border-bottom: none;
        }
        .platform-icon {
            width: 36px;
            height: 36px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }
        .platform-bilibili { background: #00a1d6; }
        .platform-wechat { background: #07c160; }
        .platform-zhihu { background: #0066ff; }
        .platform-rss { background: #f97316; }
        .update-content {
            flex: 1;
        }
        .update-title {
            font-size: 14px;
            color: #f8fafc;
            text-decoration: none;
            display: block;
            margin-bottom: 4px;
        }
        .update-title:hover {
            color: #60a5fa;
        }
        .update-meta {
            font-size: 12px;
            color: #64748b;
        }
        .empty-state {
            padding: 48px;
            text-align: center;
            color: #64748b;
        }
        .source-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .source-item {
            display: flex;
            align-items: center;
            padding: 12px;
            border-bottom: 1px solid #334155;
            gap: 12px;
        }
        .source-item:last-child {
            border-bottom: none;
        }
        .source-info {
            flex: 1;
        }
        .source-name {
            font-size: 14px;
            color: #f8fafc;
            margin-bottom: 2px;
        }
        .source-platform {
            font-size: 12px;
            color: #64748b;
        }
        .source-actions {
            display: flex;
            gap: 8px;
        }
        .btn {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: opacity 0.2s;
        }
        .btn:hover {
            opacity: 0.9;
        }
        .btn-sm {
            padding: 4px 8px;
            font-size: 12px;
        }
        .btn-danger {
            background: linear-gradient(135deg, #ef4444, #dc2626);
        }
        .btn-success {
            background: linear-gradient(135deg, #10b981, #059669);
        }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
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
        .modal.active {
            display: flex;
        }
        .modal-content {
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            width: 90%;
            max-width: 500px;
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
        .form-group input:focus,
        .form-group select:focus {
            outline: none;
            border-color: #60a5fa;
        }
        .form-actions {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
            margin-top: 20px;
        }
        .validation-result {
            padding: 10px;
            border-radius: 6px;
            margin-top: 12px;
            font-size: 13px;
            display: none;
        }
        .validation-result.success {
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .validation-result.error {
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
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
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .history-chart {
            margin-bottom: 20px;
        }
        .chart-bars {
            display: flex;
            align-items: flex-end;
            gap: 4px;
            height: 100px;
            padding-top: 20px;
        }
        .chart-bar {
            flex: 1;
            background: linear-gradient(180deg, #60a5fa, #3b82f6);
            border-radius: 4px 4px 0 0;
            min-height: 4px;
            transition: opacity 0.2s;
            position: relative;
        }
        .chart-bar:hover {
            opacity: 0.8;
        }
        .toggle-switch {
            width: 44px;
            height: 24px;
            background: #334155;
            border-radius: 12px;
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
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: transform 0.2s;
        }
        .toggle-switch.active::after {
            transform: translateX(20px);
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>信息源监控看板</h1>
            <div class="date" id="currentDate"></div>
        </div>
        <div class="header-actions">
            <button class="btn" onclick="showAddModal()">+ 添加信源</button>
            <button class="btn" onclick="refreshData()" id="refreshBtn">刷新</button>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">监控中</div>
            <div class="value" id="sourceCount">-</div>
        </div>
        <div class="stat-card">
            <div class="label">今日更新</div>
            <div class="value today" id="todayCount">-</div>
        </div>
        <div class="stat-card">
            <div class="label">总更新数</div>
            <div class="value" id="totalCount">-</div>
        </div>
        <div class="stat-card">
            <div class="label">总信源数</div>
            <div class="value" id="totalSources">-</div>
        </div>
    </div>

    <div class="content">
        <div>
            <div class="section">
                <div class="section-title">更新趋势 (近30天)</div>
                <div class="history-chart">
                    <div class="chart-bars" id="chartBars"></div>
                </div>
            </div>

            <div class="section" style="margin-top: 24px;">
                <div class="section-title">今日更新</div>
                <div class="update-list" id="updateList">
                    <div class="empty-state">加载中...</div>
                </div>
            </div>
        </div>

        <div>
            <div class="section">
                <div class="section-title">信源管理</div>
                <div class="source-list" id="sourceList">
                    <div class="empty-state">加载中...</div>
                </div>
            </div>
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
                    <option value="wechat">微信公众号</option>
                    <option value="zhihu">知乎</option>
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

            <div class="form-group" id="accountGroup" style="display:none;">
                <label>公众号ID</label>
                <input type="text" id="sourceAccount" placeholder="公众号ID">
            </div>

            <div class="form-group" id="userIdGroup" style="display:none;">
                <label>知乎用户ID</label>
                <input type="text" id="sourceUserId" placeholder="用户ID">
            </div>

            <div class="validation-result" id="validationResult"></div>

            <div class="form-actions">
                <button class="btn" onclick="hideAddModal()">取消</button>
                <button class="btn" onclick="validateAndAdd()" id="validateBtn">验证并添加</button>
            </div>
        </div>
    </div>

    <script>
        const platformIcons = {
            'bilibili': 'B',
            'wechat': 'W',
            'zhihu': 'Z',
            'rss': 'R'
        };

        const platformNames = {
            'bilibili': 'B站',
            'wechat': '微信',
            'zhihu': '知乎',
            'rss': 'RSS'
        };

        // 初始化
        document.getElementById('currentDate').textContent =
            new Date().toLocaleDateString('zh-CN', {
                year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
            });

        async function loadStats() {
            const res = await fetch('/api/stats');
            const data = await res.json();
            document.getElementById('sourceCount').textContent = data.sources;
            document.getElementById('totalSources').textContent = data.total_sources;
            document.getElementById('todayCount').textContent = data.today_updates;
            document.getElementById('totalCount').textContent = data.total_updates;
        }

        async function loadUpdates() {
            const res = await fetch('/api/updates');
            const data = await res.json();
            const listEl = document.getElementById('updateList');

            if (data.updates.length === 0) {
                listEl.innerHTML = '<div class="empty-state">今日暂无更新</div>';
                return;
            }

            listEl.innerHTML = data.updates.map(u => {
                const time = new Date(u.published_at).toLocaleTimeString('zh-CN', {
                    hour: '2-digit', minute: '2-digit'
                });
                return `
                    <div class="update-item">
                        <div class="platform-icon platform-${u.platform}">
                            ${platformIcons[u.platform] || '?'}
                        </div>
                        <div class="update-content">
                            <a href="${u.url}" target="_blank" class="update-title">${u.title}</a>
                            <div class="update-meta">${u.source_name}</div>
                        </div>
                        <div class="update-meta">${time}</div>
                    </div>
                `;
            }).join('');
        }

        async function loadSources() {
            const res = await fetch('/api/sources');
            const data = await res.json();
            const listEl = document.getElementById('sourceList');

            if (data.sources.length === 0) {
                listEl.innerHTML = '<div class="empty-state">暂无信源</div>';
                return;
            }

            listEl.innerHTML = data.sources.map(s => `
                <div class="source-item">
                    <div class="platform-icon platform-${s.platform}">
                        ${platformIcons[s.platform] || '?'}
                    </div>
                    <div class="source-info">
                        <div class="source-name">${s.name}</div>
                        <div class="source-platform">${platformNames[s.platform]}</div>
                    </div>
                    <div class="source-actions">
                        <div class="toggle-switch ${s.enabled ? 'active' : ''}" onclick="toggleSource('${s.id}', ${!s.enabled})"></div>
                        <button class="btn btn-sm btn-danger" onclick="deleteSource('${s.id}')">删除</button>
                    </div>
                </div>
            `).join('');
        }

        async function loadHistory() {
            const res = await fetch('/api/history');
            const data = await res.json();
            const maxCount = Math.max(...data.history.map(h => h.count), 1);

            document.getElementById('chartBars').innerHTML = data.history.map(h => `
                <div class="chart-bar" style="height: ${(h.count / maxCount * 100) || 4}%"
                     title="${h.date}: ${h.count}条"></div>
            `).join('');
        }

        async function refreshData() {
            const btn = document.getElementById('refreshBtn');
            btn.innerHTML = '<span class="loading"></span>';
            btn.disabled = true;

            try {
                const res = await fetch('/api/refresh');
                const data = await res.json();

                if (data.success) {
                    await Promise.all([loadStats(), loadUpdates(), loadHistory()]);
                    const msg = data.results.map(r =>
                        r.success ? `${r.name}: ${r.new_items || 0}条` : `${r.name}: 失败`
                    ).join('\\n');
                    alert('抓取完成！\\n' + msg);
                } else {
                    alert('抓取失败: ' + data.error);
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            } finally {
                btn.innerHTML = '刷新';
                btn.disabled = false;
            }
        }

        // 弹窗控制
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
            document.getElementById('sourceAccount').value = '';
            document.getElementById('sourceUserId').value = '';
            hideAllGroups();
            hideValidation();
        }

        function hideAllGroups() {
            document.getElementById('uidGroup').style.display = 'none';
            document.getElementById('urlGroup').style.display = 'none';
            document.getElementById('accountGroup').style.display = 'none';
            document.getElementById('userIdGroup').style.display = 'none';
        }

        function onPlatformChange() {
            const platform = document.getElementById('platformSelect').value;
            hideAllGroups();

            if (platform === 'bilibili') {
                document.getElementById('uidGroup').style.display = 'block';
            } else if (platform === 'rss') {
                document.getElementById('urlGroup').style.display = 'block';
            } else if (platform === 'wechat') {
                document.getElementById('accountGroup').style.display = 'block';
            } else if (platform === 'zhihu') {
                document.getElementById('userIdGroup').style.display = 'block';
            }
        }

        function showValidation(success, message) {
            const el = document.getElementById('validationResult');
            el.textContent = message;
            el.className = 'validation-result ' + (success ? 'success' : 'error');
            el.style.display = 'block';
        }

        function hideValidation() {
            document.getElementById('validationResult').style.display = 'none';
        }

        async function validateAndAdd() {
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
            } else if (platform === 'wechat') {
                data.account = document.getElementById('sourceAccount').value.trim();
            } else if (platform === 'zhihu') {
                data.user_id = document.getElementById('sourceUserId').value.trim();
            }

            const btn = document.getElementById('validateBtn');
            btn.innerHTML = '<span class="loading"></span>验证中...';
            btn.disabled = true;

            try {
                // 先验证
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

                // 再添加
                const addRes = await fetch('/api/sources/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const addData = await addRes.json();

                if (addData.success) {
                    await loadSources();
                    await loadStats();
                    hideAddModal();
                    alert('添加成功！');
                } else {
                    showValidation(false, addData.error);
                }
            } catch (e) {
                showValidation(false, '请求失败: ' + e.message);
            } finally {
                btn.innerHTML = '验证并添加';
                btn.disabled = false;
            }
        }

        async function deleteSource(id) {
            if (!confirm('确定要删除这个信源吗？')) return;

            try {
                const res = await fetch('/api/sources/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id })
                });
                const data = await res.json();

                if (data.success) {
                    await loadSources();
                    await loadStats();
                } else {
                    alert('删除失败: ' + data.error);
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

        async function toggleSource(id, enabled) {
            try {
                const res = await fetch('/api/sources/toggle', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id, enabled })
                });
                const data = await res.json();

                if (data.success) {
                    await loadSources();
                    await loadStats();
                } else {
                    alert('操作失败: ' + data.error);
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

        // 初始化
        async function init() {
            await Promise.all([loadStats(), loadUpdates(), loadSources(), loadHistory()]);
        }

        init();
        setInterval(loadUpdates, 5 * 60 * 1000);
    </script>
</body>
</html>'''


def start_server(port=8080):
    """启动服务器"""
    init_db()
    init_config()
    server = HTTPServer(('localhost', port), DashboardHandler)
    print(f"\n[OK] 看板已启动: http://localhost:{port}")
    print("按 Ctrl+C 停止\n")

    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{port}')).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.shutdown()


if __name__ == '__main__':
    print("正在初始化...")
    init_db()
    init_config()

    sources = load_sources()
    enabled_sources = [s for s in sources if s.get('enabled', True)]

    if enabled_sources:
        print(f"正在抓取 {len(enabled_sources)} 个信源的初始数据...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(fetch_all_sources(enabled_sources))
        loop.close()
        print("初始数据抓取完成！")
    else:
        print("没有启用的信源，跳过初始抓取")

    start_server()

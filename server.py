"""信息源监控看板 - Web服务器"""

import asyncio
import json
from datetime import datetime, date
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import webbrowser

from fetchers import ContentStore, fetch_all_sources, init_db
from database import get_upcoming_reminders
from config import SOURCES
import urllib.parse


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP请求处理"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == '/':
            self.serve_html()
        elif path.startswith('/themes/'):
            self.serve_theme(path)
        elif path == '/api/stats':
            self.serve_stats()
        elif path == '/api/updates':
            self.serve_updates()
        elif path == '/api/sources':
            self.serve_sources()
        elif path == '/api/history':
            self.serve_history()
        elif path == '/api/reminders':
            self.serve_reminders()
        elif path == '/api/source/detail':
            self.serve_source_detail(query)
        elif path == '/api/refresh':
            self.handle_refresh()
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """禁用日志输出"""
        pass

    def serve_html(self):
        """返回主页HTML"""
        html = Path(__file__).parent / "dashboard.html"
        if html.exists():
            content = html.read_text(encoding='utf-8')
        else:
            content = self.generate_html()

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def serve_theme(self, path):
        """返回主题CSS文件"""
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

    def serve_stats(self):
        """返回统计数据"""
        store = ContentStore()
        stats = store.get_source_stats()
        today_count = sum(s['today'] for s in stats.values())
        total_count = sum(s['total'] for s in stats.values())

        self.send_json({
            'sources': len(SOURCES),
            'today_updates': today_count,
            'total_updates': total_count,
            'source_stats': stats
        })

    def serve_updates(self):
        """返回今日更新"""
        store = ContentStore()
        updates = store.get_today_updates()

        # 添加信息源名称
        for u in updates:
            src = next((s for s in SOURCES if s['id'] == u['source_id']), None)
            u['source_name'] = src['name'] if src else u['source_id']

        self.send_json({'updates': updates})

    def serve_sources(self):
        """返回信息源列表"""
        self.send_json({
            'sources': [
                {
                    'id': s['id'],
                    'name': s['name'],
                    'platform': s['platform'],
                    'enabled': s.get('enabled', True)
                }
                for s in SOURCES
            ]
        })

    def serve_history(self):
        """返回历史数据"""
        store = ContentStore()
        history = store.get_recent_updates(30)
        self.send_json({'history': history})

    def serve_reminders(self):
        """返回人脉提醒"""
        reminders = get_upcoming_reminders()
        self.send_json(reminders)

    def serve_source_detail(self, query):
        """返回单个信源的更新历史"""
        source_id = query.get('id', [None])[0]
        if not source_id:
            self.send_json({'error': 'Missing source id'})
            return

        store = ContentStore()
        updates = store.get_updates_by_source(source_id, days=30)
        self.send_json({'updates': updates})

    def handle_refresh(self):
        """手动刷新"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(fetch_all_sources(SOURCES))
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

    def send_json(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def generate_html(self):
        """生成HTML页面（内置备用）"""
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
        }
        .header h1 {
            font-size: 24px;
            margin-bottom: 8px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header .date {
            color: #94a3b8;
            font-size: 14px;
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
            transition: transform 0.2s;
        }
        .stat-card:hover {
            transform: translateY(-2px);
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
            background: #1e293b;
            border-radius: 12px;
            border: 1px solid #334155;
            overflow: hidden;
        }
        .update-item {
            padding: 16px 20px;
            border-bottom: 1px solid #334155;
            display: flex;
            align-items: flex-start;
            gap: 12px;
            transition: background 0.2s;
        }
        .update-item:last-child {
            border-bottom: none;
        }
        .update-item:hover {
            background: #334155;
        }
        .platform-icon {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
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
            font-size: 15px;
            color: #f8fafc;
            margin-bottom: 4px;
            text-decoration: none;
            display: block;
        }
        .update-title:hover {
            color: #60a5fa;
        }
        .update-meta {
            font-size: 13px;
            color: #94a3b8;
        }
        .update-time {
            font-size: 12px;
            color: #64748b;
            white-space: nowrap;
        }
        .empty-state {
            padding: 48px;
            text-align: center;
            color: #64748b;
        }
        .btn {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: opacity 0.2s;
        }
        .btn:hover {
            opacity: 0.9;
        }
        .refresh-btn {
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 14px 24px;
            font-size: 15px;
            border-radius: 50px;
            box-shadow: 0 4px 20px rgba(59, 130, 246, 0.3);
        }
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .history-chart {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #334155;
            margin-bottom: 24px;
        }
        .chart-bars {
            display: flex;
            align-items: flex-end;
            gap: 4px;
            height: 120px;
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
        .chart-bar::before {
            content: attr(data-count);
            position: absolute;
            top: -20px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 11px;
            color: #94a3b8;
            opacity: 0;
            transition: opacity 0.2s;
        }
        .chart-bar:hover::before {
            opacity: 1;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📡 信息源监控看板</h1>
        <div class="date" id="currentDate"></div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">监控源数量</div>
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
    </div>

    <div class="content">
        <div class="history-chart">
            <div class="section-title">更新趋势 (近30天)</div>
            <div class="chart-bars" id="chartBars"></div>
        </div>

        <div class="section-title">今日更新</div>
        <div class="update-list" id="updateList">
            <div class="empty-state">加载中...</div>
        </div>
    </div>

    <button class="btn refresh-btn" onclick="refreshData()" id="refreshBtn">
        🔄 刷新数据
    </button>

    <script>
        // 设置日期
        document.getElementById('currentDate').textContent =
            new Date().toLocaleDateString('zh-CN', {
                year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
            });

        // 平台图标映射
        const platformIcons = {
            'bilibili': '📺',
            'wechat': '💬',
            'zhihu': '🤔',
            'rss': '📰'
        };

        // 加载统计数据
        async function loadStats() {
            const res = await fetch('/api/stats');
            const data = await res.json();
            document.getElementById('sourceCount').textContent = data.sources;
            document.getElementById('todayCount').textContent = data.today_updates;
            document.getElementById('totalCount').textContent = data.total_updates;
        }

        // 加载更新列表
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
                            ${platformIcons[u.platform] || '📄'}
                        </div>
                        <div class="update-content">
                            <a href="${u.url}" target="_blank" class="update-title">${u.title}</a>
                            <div class="update-meta">${u.source_name}</div>
                        </div>
                        <div class="update-time">${time}</div>
                    </div>
                `;
            }).join('');
        }

        // 加载历史图表
        async function loadHistory() {
            const res = await fetch('/api/history');
            const data = await res.json();
            const maxCount = Math.max(...data.history.map(h => h.count), 1);

            document.getElementById('chartBars').innerHTML = data.history.map(h => `
                <div class="chart-bar" style="height: ${(h.count / maxCount * 100) || 4}%"
                     data-count="${h.count}" title="${h.date}: ${h.count}条"></div>
            `).join('');
        }

        // 刷新数据
        async function refreshData() {
            const btn = document.getElementById('refreshBtn');
            btn.innerHTML = '<span class="loading"></span>抓取中...';
            btn.disabled = true;

            try {
                const res = await fetch('/api/refresh');
                const data = await res.json();

                if (data.success) {
                    await Promise.all([loadStats(), loadUpdates(), loadHistory()]);
                    alert(`抓取完成！\\n${data.results.map(r =>
                        r.success ? `${r.name}: ${r.new_items || 0}条新内容` : `${r.name}: 失败`
                    ).join('\\n')}`);
                } else {
                    alert('抓取失败: ' + data.error);
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            } finally {
                btn.innerHTML = '🔄 刷新数据';
                btn.disabled = false;
            }
        }

        // 初始化
        async function init() {
            await Promise.all([loadStats(), loadUpdates(), loadHistory()]);
        }

        init();
        // 每5分钟自动刷新
        setInterval(loadUpdates, 5 * 60 * 1000);
    </script>
</body>
</html>'''


def start_server(port=8080):
    """启动服务器"""
    init_db()
    server = HTTPServer(('localhost', port), DashboardHandler)
    print(f"\n[OK] 看板已启动: http://localhost:{port}")
    print("按 Ctrl+C 停止\n")

    # 自动打开浏览器
    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{port}')).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.shutdown()


if __name__ == '__main__':
    # 首次运行先抓取数据
    print("正在初始化数据库并抓取初始数据...")
    init_db()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(fetch_all_sources(SOURCES))
    loop.close()

    print("初始数据抓取完成！")
    start_server()

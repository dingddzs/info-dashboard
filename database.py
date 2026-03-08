"""数据库管理模块"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "updates.db"


def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 内容表 - 增加content和summary字段
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT,
            content TEXT,           -- 完整内容（简介/正文）
            summary TEXT,           -- AI总结
            published_at TIMESTAMP,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, title, published_at)
        )
    """)

    # 创建索引加速查询
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON updates(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON updates(published_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON updates(title)")

    # 抓取日志表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fetch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            new_items INTEGER DEFAULT 0,
            status TEXT DEFAULT 'success'
        )
    """)

    # 人脉管理表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
            birthday TEXT,
            identity TEXT,
            important_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 人脉待办事项表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL,
            task_content TEXT NOT NULL,
            due_date TEXT,
            is_completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
        )
    """)

    # 忽略的提醒表（用于存储用户打勾忽略的提醒）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ignored_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_type TEXT NOT NULL,
            contact_id INTEGER,
            todo_id INTEGER,
            ignored_year INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 迁移：为已有数据库添加 gender 列
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN gender TEXT")
    except:
        pass  # 列已存在

    conn.commit()
    conn.close()


class ContentStore:
    """内容存储管理"""

    def __init__(self):
        self.db_path = DB_PATH
        init_db()

    def save_updates(self, source_id: str, platform: str, items: list):
        """保存更新内容，返回新增数量"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        new_count = 0
        for item in items:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO updates
                    (source_id, platform, title, url, content, published_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    source_id,
                    platform,
                    item['title'],
                    item.get('url'),
                    item.get('content', ''),
                    item.get('published_at')
                ))
                if cursor.rowcount > 0:
                    new_count += 1
            except Exception as e:
                print(f"保存失败: {e}")

        conn.commit()
        conn.close()
        return new_count

    def update_summary(self, update_id: int, summary: str):
        """更新AI总结"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE updates SET summary = ? WHERE id = ?", (summary, update_id))
        conn.commit()
        conn.close()

    def get_today_updates(self):
        """获取今日更新（用于首页展示）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        today = date.today().isoformat()

        # 只返回今天的更新，不是今天的数据不显示
        cursor.execute("""
            SELECT id, source_id, platform, title, url, content, summary, published_at
            FROM updates
            WHERE date(published_at) = ?
            ORDER BY published_at DESC
        """, (today,))

        rows = cursor.fetchall()
        conn.close()

        return [{
            'id': r[0],
            'source_id': r[1],
            'platform': r[2],
            'title': r[3],
            'url': r[4],
            'content': r[5],
            'summary': r[6],
            'published_at': r[7]
        } for r in rows]

    def get_updates_by_source(self, source_id: str, days=30, search_query=None):
        """获取指定信源的更新历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if search_query:
            # 搜索模式
            cursor.execute("""
                SELECT id, source_id, platform, title, url, published_at
                FROM updates
                WHERE source_id = ? AND (title LIKE ? OR content LIKE ?)
                ORDER BY published_at DESC
                LIMIT 100
            """, (source_id, f'%{search_query}%', f'%{search_query}%'))
        else:
            # 普通模式 - 最近N天
            cursor.execute("""
                SELECT id, source_id, platform, title, url, published_at
                FROM updates
                WHERE source_id = ? AND published_at >= datetime('now', '-{} days')
                ORDER BY published_at DESC
            """.format(days), (source_id,))

        rows = cursor.fetchall()
        conn.close()

        return [{
            'id': r[0],
            'source_id': r[1],
            'platform': r[2],
            'title': r[3],
            'url': r[4],
            'published_at': r[5]
        } for r in rows]

    def get_source_stats(self):
        """获取各信源统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        today = date.today().isoformat()

        cursor.execute("""
            SELECT source_id, COUNT(*) as total,
                   SUM(CASE WHEN date(published_at) = ? THEN 1 ELSE 0 END) as today_count
            FROM updates
            GROUP BY source_id
        """, (today,))

        rows = cursor.fetchall()
        conn.close()

        return {r[0]: {
            'total': r[1],
            'today': r[2]
        } for r in rows}

    def search_all(self, query: str, limit=50):
        """全局搜索"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, source_id, platform, title, url, published_at
            FROM updates
            WHERE title LIKE ? OR content LIKE ? OR summary LIKE ?
            ORDER BY published_at DESC
            LIMIT ?
        """, (f'%{query}%', f'%{query}%', f'%{query}%', limit))

        rows = cursor.fetchall()
        conn.close()

        return [{
            'id': r[0],
            'source_id': r[1],
            'platform': r[2],
            'title': r[3],
            'url': r[4],
            'published_at': r[5]
        } for r in rows]

    def get_recent_updates(self, days=30):
        """获取最近N天的更新统计（用于图表）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT date(published_at) as date, COUNT(*) as count
            FROM updates
            WHERE published_at >= datetime('now', '-{} days')
            GROUP BY date(published_at)
            ORDER BY date
        """.format(days))

        rows = cursor.fetchall()
        conn.close()

        return [{'date': r[0], 'count': r[1]} for r in rows]


class ContactStore:
    """人脉管理存储"""

    def __init__(self):
        self.db_path = DB_PATH
        init_db()

    # ========== 人物管理 ==========

    def add_contact(self, name: str, gender: str = None, birthday: str = None, identity: str = None, important_info: str = None):
        """添加人物"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO contacts (name, gender, birthday, identity, important_info)
            VALUES (?, ?, ?, ?, ?)
        """, (name, gender, birthday, identity, important_info))
        contact_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return contact_id

    def get_contacts(self):
        """获取所有人物"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, gender, birthday, identity, important_info
            FROM contacts
            ORDER BY name
        """)
        rows = cursor.fetchall()
        conn.close()

        return [{
            'id': r[0],
            'name': r[1],
            'gender': r[2],
            'birthday': r[3],
            'identity': r[4],
            'important_info': r[5]
        } for r in rows]

    def get_contact(self, contact_id: int):
        """获取单个人物详情"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, gender, birthday, identity, important_info
            FROM contacts WHERE id = ?
        """, (contact_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None
        return {
            'id': row[0],
            'name': row[1],
            'gender': row[2],
            'birthday': row[3],
            'identity': row[4],
            'important_info': row[5]
        }

    def update_contact(self, contact_id: int, name: str = None, gender: str = None, birthday: str = None, identity: str = None, important_info: str = None):
        """更新人物信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        contact = self.get_contact(contact_id)
        if not contact:
            conn.close()
            return False

        name = name if name is not None else contact['name']
        gender = gender if gender is not None else contact['gender']
        birthday = birthday if birthday is not None else contact['birthday']
        identity = identity if identity is not None else contact['identity']
        important_info = important_info if important_info is not None else contact['important_info']

        cursor.execute("""
            UPDATE contacts SET name = ?, gender = ?, birthday = ?, identity = ?, important_info = ?
            WHERE id = ?
        """, (name, gender, birthday, identity, important_info, contact_id))
        conn.commit()
        conn.close()
        return True

    def delete_contact(self, contact_id: int):
        """删除人物（联级删除待办）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
        conn.close()
        return True

    # ========== 待办事项管理 ==========

    def add_todo(self, contact_id: int, task_content: str, due_date: str = None):
        """添加待办"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO contact_todos (contact_id, task_content, due_date)
            VALUES (?, ?, ?)
        """, (contact_id, task_content, due_date))
        todo_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return todo_id

    def get_todos_by_contact(self, contact_id: int):
        """获取某人的所有待办"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, task_content, due_date, is_completed
            FROM contact_todos
            WHERE contact_id = ?
            ORDER BY due_date, id DESC
        """, (contact_id,))
        rows = cursor.fetchall()
        conn.close()

        return [{
            'id': r[0],
            'task_content': r[1],
            'due_date': r[2],
            'is_completed': bool(r[3])
        } for r in rows]

    def toggle_todo(self, todo_id: int, is_completed: bool):
        """切换待办完成状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE contact_todos SET is_completed = ? WHERE id = ?
        """, (1 if is_completed else 0, todo_id))
        conn.commit()
        conn.close()
        return True

    def delete_todo(self, todo_id: int):
        """删除待办"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contact_todos WHERE id = ?", (todo_id,))
        conn.commit()
        conn.close()
        return True


# ========== 提醒引擎 ==========

def is_reminder_ignored(reminder_type: str, contact_id: int = None, todo_id: int = None, year: int = None):
    """检查提醒是否被用户忽略"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if reminder_type == 'birthday' and contact_id:
        cursor.execute("""
            SELECT id FROM ignored_reminders
            WHERE reminder_type = 'birthday' AND contact_id = ? AND ignored_year = ?
        """, (contact_id, year))
    elif reminder_type == 'todo' and todo_id:
        cursor.execute("""
            SELECT id FROM ignored_reminders
            WHERE reminder_type = 'todo' AND todo_id = ?
        """, (todo_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def ignore_reminder(reminder_type: str, contact_id: int = None, todo_id: int = None, year: int = None):
    """添加忽略提醒记录"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ignored_reminders (reminder_type, contact_id, todo_id, ignored_year)
        VALUES (?, ?, ?, ?)
    """, (reminder_type, contact_id, todo_id, year))
    conn.commit()
    conn.close()

def get_upcoming_reminders():
    """
    获取未来10天内的提醒（排除已忽略的）
    返回: {
        'birthdays': [{'contact_id', 'name', 'birthday', 'days_until'}],
        'todos': [{'todo_id', 'contact_id', 'contact_name', 'task_content', 'due_date', 'days_until'}]
    }
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = date.today()
    current_year = today.year
    reminders = {'birthdays': [], 'todos': []}

    # 1. 生日提醒（忽略年份，只看月日）
    cursor.execute("""
        SELECT id, name, birthday FROM contacts
        WHERE birthday IS NOT NULL AND birthday != ''
    """)
    for row in cursor.fetchall():
        contact_id, name, birthday_str = row
        try:
            # 解析生日 (YYYY-MM-DD)
            birth_date = datetime.strptime(birthday_str, '%Y-%m-%d').date()
            # 计算今年的生日
            this_year_birthday = birth_date.replace(year=today.year)
            # 如果今年生日已过，算明年的
            if this_year_birthday < today:
                this_year_birthday = birth_date.replace(year=today.year + 1)

            days_until = (this_year_birthday - today).days
            if 0 <= days_until <= 10:
                # 检查是否已被忽略
                ignore_year = this_year_birthday.year
                if not is_reminder_ignored('birthday', contact_id=contact_id, year=ignore_year):
                    reminders['birthdays'].append({
                        'contact_id': contact_id,
                        'name': name,
                        'birthday': birthday_str,
                        'days_until': days_until,
                        'ignore_year': ignore_year
                    })
        except:
            continue

    # 2. 待办提醒（未来10天内未完成）
    cursor.execute("""
        SELECT t.id, t.contact_id, c.name, t.task_content, t.due_date
        FROM contact_todos t
        JOIN contacts c ON t.contact_id = c.id
        WHERE t.is_completed = 0 AND t.due_date IS NOT NULL
    """)
    for row in cursor.fetchall():
        todo_id, contact_id, contact_name, task_content, due_date_str = row
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            days_until = (due_date - today).days
            if 0 <= days_until <= 10:
                # 检查是否已被忽略
                if not is_reminder_ignored('todo', todo_id=todo_id):
                    reminders['todos'].append({
                        'todo_id': todo_id,
                        'contact_id': contact_id,
                        'contact_name': contact_name,
                        'task_content': task_content,
                        'due_date': due_date_str,
                        'days_until': days_until
                    })
        except:
            continue

    conn.close()

    # 按紧急程度排序（天数少的在前）
    reminders['birthdays'].sort(key=lambda x: x['days_until'])
    reminders['todos'].sort(key=lambda x: x['days_until'])

    return reminders

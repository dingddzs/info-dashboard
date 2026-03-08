"""信息源抓取模块 - 支持多平台"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
import feedparser
from bilibili_api import user as bili_user, video as bili_video

from database import ContentStore, init_db
from summarizer import summarize_content


class BilibiliFetcher:
    """B站抓取器"""

    @staticmethod
    async def fetch(uid: int, name: str = None):
        """获取UP主最新视频"""
        try:
            u = bili_user.User(uid=uid)
            result = await u.get_videos(pn=1, ps=20)

            videos = []
            for item in result.get('list', {}).get('vlist', []):
                bvid = item.get('bvid')

                # 获取视频详细信息（包括简介）
                try:
                    v = bili_video.Video(bvid=bvid)
                    info = await v.get_info()
                    description = info.get('desc', '')
                except:
                    description = item.get('description', '')

                videos.append({
                    'title': item.get('title'),
                    'url': f"https://www.bilibili.com/video/{bvid}",
                    'content': description,
                    'published_at': datetime.fromtimestamp(item.get('created', 0)),
                    'bvid': bvid
                })

            return {
                'success': True,
                'name': name or str(uid),
                'items': videos
            }
        except Exception as e:
            return {
                'success': False,
                'name': name or str(uid),
                'error': str(e),
                'items': []
            }


class RSSFetcher:
    """RSS/博客抓取器"""

    @staticmethod
    def fetch(url: str, name: str = None):
        """获取RSS订阅"""
        try:
            feed = feedparser.parse(url)
            items = []

            for entry in feed.entries[:20]:
                # 解析发布时间
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])
                else:
                    published = datetime.now()

                # 获取内容
                content = ''
                if hasattr(entry, 'content'):
                    content = entry.content[0].value if entry.content else ''
                elif hasattr(entry, 'summary'):
                    content = entry.summary

                items.append({
                    'title': entry.get('title', '无标题'),
                    'url': entry.get('link', ''),
                    'content': content,
                    'published_at': published
                })

            return {
                'success': True,
                'name': name or feed.feed.get('title', url),
                'items': items
            }
        except Exception as e:
            return {
                'success': False,
                'name': name or url,
                'error': str(e),
                'items': []
            }


async def fetch_all_sources(sources: list, generate_summary: bool = True):
    """批量抓取所有信息源"""
    store = ContentStore()
    results = []

    for src in sources:
        if not src.get('enabled', True):
            continue

        platform = src['platform']
        source_id = src['id']
        name = src.get('name', source_id)

        try:
            if platform == 'bilibili':
                result = await BilibiliFetcher.fetch(src['uid'], name)
            elif platform == 'rss':
                result = RSSFetcher.fetch(src['url'], name)
            else:
                result = {'success': False, 'error': f'不支持的平台: {platform}', 'items': []}

            if result['success']:
                # 只保存最近30天内的内容
                cutoff = datetime.now() - timedelta(days=30)
                recent_items = [
                    item for item in result['items']
                    if item.get('published_at', datetime.now()) > cutoff
                ]

                # 为每个item生成摘要
                if generate_summary:
                    for item in recent_items:
                        item['summary'] = summarize_content(
                            item['title'],
                            item.get('content', ''),
                            platform
                        )

                new_count = store.save_updates(source_id, platform, recent_items)

                results.append({
                    'id': source_id,
                    'name': name,
                    'platform': platform,
                    'success': True,
                    'new_items': new_count
                })
            else:
                results.append({
                    'id': source_id,
                    'name': name,
                    'platform': platform,
                    'success': False,
                    'error': result.get('error')
                })

        except Exception as e:
            results.append({
                'id': source_id,
                'name': name,
                'platform': platform,
                'success': False,
                'error': str(e)
            })

    return results


if __name__ == '__main__':
    # 测试
    from config_manager import load_sources

    init_db()
    sources = load_sources()
    bili_sources = [s for s in sources if s['platform'] == 'bilibili']
    results = asyncio.run(fetch_all_sources(bili_sources))

    print("\n抓取结果:")
    for r in results:
        status = "✓" if r['success'] else "✗"
        print(f"{status} {r['name']}: {r.get('new_items', 0)} 条新内容")

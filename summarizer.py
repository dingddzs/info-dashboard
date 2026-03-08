"""AI总结模块 - 为内容生成摘要"""

import re


def summarize_content(title: str, content: str, platform: str) -> str:
    """
    生成内容摘要
    实际项目中可以接入OpenAI API、文心一言等
    这里先用简单的规则实现
    """
    if not content:
        # 只有标题时，返回标题的前50字
        return title[:50] + "..." if len(title) > 50 else title

    # 清理内容
    content = content.strip()

    # 根据不同平台处理
    if platform == 'bilibili':
        # B站视频简介通常有固定格式
        # 提取前几句话
        sentences = re.split(r'[。！？\n]', content)
        summary_sentences = []
        char_count = 0

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            # 过滤掉常见的无意义内容
            if any(skip in sent for skip in ['一键三连', '关注', '点赞', '投币', '收藏', '转发', '弹幕', '评论']):
                continue
            if len(sent) < 5:  # 太短的句子跳过
                continue

            summary_sentences.append(sent)
            char_count += len(sent)

            if char_count >= 100:  # 摘要长度约100字
                break

        if summary_sentences:
            return '。'.join(summary_sentences) + '。'

    # 通用处理 - 提取前150字
    clean_text = re.sub(r'<[^>]+>', '', content)  # 去除HTML标签
    clean_text = re.sub(r'\s+', ' ', clean_text)  # 合并空白

    if len(clean_text) <= 150:
        return clean_text

    # 找第150字后的第一个句号
    trunc_point = 150
    next_period = clean_text.find('。', trunc_point)
    if next_period != -1 and next_period - trunc_point < 50:
        return clean_text[:next_period + 1]

    return clean_text[:150] + "..."


def batch_summarize(items: list) -> list:
    """批量生成摘要"""
    for item in items:
        if not item.get('summary'):
            item['summary'] = summarize_content(
                item.get('title', ''),
                item.get('content', ''),
                item.get('platform', 'unknown')
            )
    return items


if __name__ == '__main__':
    # 测试
    test_cases = [
        {
            'title': '【巫师】美国干伊朗02',
            'content': '本期视频深度解析美伊冲突背后的资本博弈...',
            'platform': 'bilibili'
        },
        {
            'title': '技术周刊第10期',
            'content': '<p>本周技术圈发生了几件大事...</p>',
            'platform': 'rss'
        }
    ]

    for tc in test_cases:
        print(f"标题: {tc['title']}")
        print(f"摘要: {summarize_content(tc['title'], tc['content'], tc['platform'])}")
        print()

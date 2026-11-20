"""把零散的口述记录编排成一本「书」的结构，供成书预览页与 PDF 导出复用。"""

from datetime import datetime

from app.models import Project
from app.question_bank import TOPIC_MAP, TOPIC_ORDER
from app.services.diff_service import summarize


def _distribute_photos(photos: list, chapter_count: int) -> list[list]:
    buckets: list[list] = [[] for _ in range(max(chapter_count, 1))]
    for index, photo in enumerate(photos):
        buckets[index % len(buckets)].append(photo)
    return buckets


def _story_items(stories: list) -> list[dict]:
    """给每段故事挂上原声地址与润色说明，让成书也能「听见」和「核对」。"""
    return [
        {
            "story": story,
            "audio_url": f"/media/audio/{story.audio_filename}" if story.audio_filename else "",
            "summary": summarize(story.raw_text, story.polished_text),
        }
        for story in stories
    ]


def build_book(project: Project) -> dict:
    grouped: dict[str, list] = {key: [] for key in TOPIC_ORDER}
    for story in project.stories:
        if story.display_text:
            grouped.setdefault(story.topic, []).append(story)

    chapters = []
    for key in TOPIC_ORDER:
        stories = grouped.get(key, [])
        if not stories:
            continue
        topic = TOPIC_MAP.get(key)
        chapters.append(
            {
                "key": key,
                "name": topic.name if topic else key,
                "subtitle": topic.subtitle if topic else "",
                "emoji": topic.emoji if topic else "📖",
                "stories": _story_items(stories),
            }
        )

    for key, stories in grouped.items():
        if key not in TOPIC_ORDER and stories:
            chapters.append(
                {
                    "key": key,
                    "name": key,
                    "subtitle": "",
                    "emoji": "📖",
                    "stories": _story_items(stories),
                }
            )

    photo_buckets = _distribute_photos(list(project.photos), len(chapters))
    for chapter, bucket in zip(chapters, photo_buckets):
        chapter["photos"] = bucket

    total_chars = sum(len(s.display_text) for s in project.stories)
    return {
        "project": project,
        "chapters": chapters,
        "total_chars": total_chars,
        "story_count": len(project.stories),
        "has_content": bool(chapters),
        "generated_at": datetime.now(),
        "signature": _signature(project),
    }


def _signature(project: Project) -> str:
    who = project.interviewer_name.strip() or "家人"
    whom = project.narrator_name.strip() or "长辈"
    return f"本书由 {who} 献给 {whom}"
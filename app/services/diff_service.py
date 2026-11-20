"""润色透明度：把 AI 相对原话改了什么，逐字摊开给家人看。

这个模块不做任何美化，只回答一个问题：
「AI 到底动了哪些字？」——因为「不瞎编」必须可验证，才构成信任。
"""

import difflib
from dataclasses import dataclass


@dataclass
class Segment:
    text: str
    kind: str  # same / add / del


def _opcodes(raw: str, polished: str) -> list[tuple]:
    if not raw or not polished:
        return []
    return difflib.SequenceMatcher(None, raw, polished, autojunk=False).get_opcodes()


def build_diff(raw: str, polished: str) -> dict:
    """返回可直接喂给模板的对照数据。

    segments 按 polished 顺序排列，del 片段表示原话里被删掉的字，
    前端用删除线呈现，让用户看得见「AI 拿走了什么」。
    """
    raw = (raw or "").strip()
    polished = (polished or "").strip()

    if not raw or not polished or raw == polished:
        return {
            "has_change": False,
            "segments": [Segment(polished, "same")] if polished else [],
            "change_count": 0,
            "added": 0,
            "removed": 0,
            "fidelity": 100,
            "length": len(polished),
            "spans": [],
        }

    segments: list[Segment] = []
    change_count = 0
    added = 0
    removed = 0
    unchanged = 0
    spans: list[dict] = []
    cursor = 0

    for tag, i1, i2, j1, j2 in _opcodes(raw, polished):
        if tag == "equal":
            text = polished[j1:j2]
            if text:
                segments.append(Segment(text, "same"))
                unchanged += len(text)
                cursor += len(text)
            continue

        change_count += 1
        old_text = raw[i1:i2]
        new_text = polished[j1:j2]

        if old_text:
            segments.append(Segment(old_text, "del"))
            removed += len(old_text)
        if new_text:
            segments.append(Segment(new_text, "add"))
            added += len(new_text)
            spans.append({"start": cursor, "end": cursor + len(new_text)})
            cursor += len(new_text)
        else:
            spans.append({"start": cursor, "end": cursor})

    fidelity = round(unchanged / len(polished) * 100) if polished else 100

    return {
        "has_change": change_count > 0,
        "segments": segments,
        "change_count": change_count,
        "added": added,
        "removed": removed,
        "fidelity": min(fidelity, 100),
        "length": len(polished),
        "spans": spans,
    }


def summarize(raw: str, polished: str) -> str:
    """给出一句话结论，用在故事卡片和成书页脚。"""
    diff = build_diff(raw, polished)
    if not diff["has_change"]:
        return "原话未改动"
    parts = []
    if diff["added"]:
        parts.append(f"增 {diff['added']} 字")
    if diff["removed"]:
        parts.append(f"删 {diff['removed']} 字")
    detail = f"（{'、'.join(parts)}）" if parts else ""
    return f"改动 {diff['change_count']} 处{detail}，原话保留 {diff['fidelity']}%"
import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import UPLOAD_DIR, settings
from app.db import get_db
from app.models import Photo, Story
from app.question_bank import QUESTION_MAP, TOPIC_MAP, TOPIC_ORDER, pick_next_question, suggest_topic
from app.routers.pages import find_project, project_metrics
from app.services import ai_asr, ai_llm
from app.services.diff_service import build_diff, summarize

router = APIRouter(prefix="/api", tags=["api"])

AUDIO_DIR = UPLOAD_DIR / "audio"
PHOTO_DIR = UPLOAD_DIR / "photos"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_SUFFIX = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


def _story_payload(story: Story) -> dict:
    diff = build_diff(story.raw_text, story.polished_text)
    return {
        "id": story.id,
        "topic": story.topic,
        "topic_name": TOPIC_MAP[story.topic].name if story.topic in TOPIC_MAP else story.topic,
        "question": story.question,
        "raw_text": story.raw_text,
        "polished_text": story.polished_text,
        "provider": story.provider,
        "created_at": story.created_at.strftime("%Y-%m-%d %H:%M") if story.created_at else "",
        "audio_url": f"/media/audio/{story.audio_filename}" if story.audio_filename else "",
        "diff": {
            "has_change": diff["has_change"],
            "segments": [{"text": s.text, "kind": s.kind} for s in diff["segments"]],
            "change_count": diff["change_count"],
            "added": diff["added"],
            "removed": diff["removed"],
            "fidelity": diff["fidelity"],
            "length": diff["length"],
            "spans": diff["spans"],
        },
        "summary": summarize(story.raw_text, story.polished_text),
    }


async def _save_audio(audio: UploadFile) -> Path:
    suffix = AUDIO_SUFFIX.get((audio.content_type or "").split(";")[0], ".webm")
    filename = f"{uuid.uuid4().hex}{suffix}"
    target = AUDIO_DIR / filename

    limit = settings.max_audio_mb * 1024 * 1024
    size = 0
    with target.open("wb") as fh:
        while chunk := await audio.read(64 * 1024):
            size += len(chunk)
            if size > limit:
                fh.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"录音超过 {settings.max_audio_mb}MB，请分段录制")
            fh.write(chunk)
    return target


@router.get("/projects/{token}/metrics")
def project_metrics_api(token: str, db: Session = Depends(get_db)):
    project = find_project(db, token)
    return {"metrics": project_metrics(project)}


@router.get("/projects/{token}/question")
def next_question(token: str, topic: str = "", db: Session = Depends(get_db)):
    project = find_project(db, token)
    if not topic:
        answered = [s.topic for s in project.stories]
        topic = suggest_topic(answered)

    if topic not in TOPIC_MAP:
        raise HTTPException(status_code=400, detail="未知的主题")

    answered_ids = [
        qid
        for qid, q in QUESTION_MAP.items()
        if q.topic == topic and any(s.question == q.text for s in project.stories)
    ]
    question = pick_next_question(topic, answered_ids)
    return {
        "topic": topic,
        "topic_name": TOPIC_MAP[topic].name,
        "finished": question is None,
        "question": (
            {"id": question.id, "text": question.text, "kind": question.kind}
            if question
            else None
        ),
    }


@router.post("/projects/{token}/stories")
async def create_story(
    token: str,
    topic: str = Form(...),
    question: str = Form(""),
    text: str = Form(""),
    vivid: bool = Form(False),
    audio: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    project = find_project(db, token)
    if topic not in TOPIC_MAP:
        raise HTTPException(status_code=400, detail="未知的主题")

    raw_text = text.strip()
    audio_filename = ""
    asr_error = ""

    if audio is not None and audio.filename:
        audio_path = await _save_audio(audio)
        audio_filename = audio_path.name
        if not raw_text:
            result = await asyncio.to_thread(ai_asr.transcribe, audio_path)
            raw_text = result.text
            asr_error = result.error

    if not raw_text:
        raise HTTPException(
            status_code=400,
            detail=asr_error or "没有收到内容，请录音或直接输入文字",
        )

    polished = await asyncio.to_thread(ai_llm.polish_story, raw_text, question, vivid)

    story = Story(
        project_id=project.id,
        topic=topic,
        question=question.strip(),
        raw_text=raw_text,
        polished_text=polished.text,
        audio_filename=audio_filename,
        provider=polished.provider,
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    return {
        "story": _story_payload(story),
        "polish_ok": polished.ai_generated,
        "polish_error": polished.error,
        "asr_error": asr_error,
    }


@router.patch("/stories/{story_id}")
def update_story(
    story_id: int,
    polished_text: str = Form(""),
    db: Session = Depends(get_db),
):
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="故事不存在")
    story.polished_text = polished_text.strip()
    db.commit()
    db.refresh(story)
    return {"story": _story_payload(story)}


@router.post("/stories/{story_id}/repolish")
async def repolish(story_id: int, vivid: bool = Form(False), db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="故事不存在")
    result = await asyncio.to_thread(ai_llm.polish_story, story.raw_text, story.question, vivid)
    story.polished_text = result.text
    story.provider = result.provider
    db.commit()
    db.refresh(story)
    return {"story": _story_payload(story), "polish_ok": result.ai_generated, "polish_error": result.error}


@router.post("/stories/{story_id}/followup")
async def followup(story_id: int, db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="故事不存在")
    topic_name = TOPIC_MAP[story.topic].name if story.topic in TOPIC_MAP else story.topic
    result = await asyncio.to_thread(ai_llm.generate_followup, story.display_text, topic_name)
    return {
        "question": result.text,
        "provider": result.provider,
        "ai_generated": result.ai_generated,
        "note": "" if result.ai_generated else (result.error or "AI 不可用，已改用本地追问模板"),
    }


@router.delete("/stories/{story_id}")
def delete_story(story_id: int, db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="故事不存在")
    if story.audio_filename:
        (AUDIO_DIR / story.audio_filename).unlink(missing_ok=True)
    db.delete(story)
    db.commit()
    return {"ok": True}


@router.post("/projects/{token}/photos")
async def upload_photo(
    token: str,
    caption: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = find_project(db, token)
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="只能上传图片文件")

    suffix = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{suffix}"
    target = PHOTO_DIR / filename

    limit = settings.max_photo_mb * 1024 * 1024
    size = 0
    with target.open("wb") as fh:
        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > limit:
                fh.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"照片超过 {settings.max_photo_mb}MB")
            fh.write(chunk)

    photo = Photo(
        project_id=project.id,
        filename=filename,
        caption=caption.strip(),
        sort_index=len(project.photos),
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return {
        "photo": {
            "id": photo.id,
            "url": f"/media/photos/{photo.filename}",
            "caption": photo.caption,
        }
    }


@router.delete("/photos/{photo_id}")
def delete_photo(photo_id: int, db: Session = Depends(get_db)):
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="照片不存在")
    (PHOTO_DIR / photo.filename).unlink(missing_ok=True)
    db.delete(photo)
    db.commit()
    return {"ok": True}


@router.get("/topics")
def list_topics():
    return {
        "topics": [
            {"key": t.key, "name": t.name, "emoji": t.emoji, "subtitle": t.subtitle}
            for t in sorted(TOPIC_MAP.values(), key=lambda x: TOPIC_ORDER.index(x.key))
        ]
    }
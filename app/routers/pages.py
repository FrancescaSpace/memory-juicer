import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db import get_db
from app.models import Project, Story
from app.question_bank import KIND_LABELS, TOPICS, TOPIC_MAP, TOPIC_ORDER
from app.services.book_service import build_book
from app.services.diff_service import build_diff, summarize
from app.services.pdf_service import PdfError, export_book_pdf

APP_DIR = Path(__file__).resolve().parent.parent


def asset_url(path: str) -> str:
    stamp = 0
    try:
        stamp = int((APP_DIR / "static" / path).stat().st_mtime)
    except OSError:
        pass
    return f"/static/{path}?v={stamp}"


templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
templates.env.globals.update(
    asset_url=asset_url,
    brand_name=settings.brand_name,
    brand_en=settings.brand_en,
    brand_slogan=settings.brand_slogan,
    kind_labels=KIND_LABELS,
)

router = APIRouter()

SPEECH_CHARS_PER_MINUTE = 180


def find_project(db: Session, token: str) -> Project:
    project = db.scalar(select(Project).where(Project.token == token))
    if project is None:
        raise HTTPException(status_code=404, detail="这本回忆录不存在或链接已失效")
    return project


def topic_stats(project: Project) -> list[dict]:
    counts = {key: 0 for key in TOPIC_ORDER}
    for story in project.stories:
        counts[story.topic] = counts.get(story.topic, 0) + 1
    return [
        {
            "key": t.key,
            "name": t.name,
            "emoji": t.emoji,
            "subtitle": t.subtitle,
            "count": counts.get(t.key, 0),
        }
        for t in TOPICS
    ]


def project_metrics(project: Project) -> dict:
    """记忆温度：只读现有数据，不改表结构。

    时长按口述语速估算（约 180 字/分钟），用于给家人一个「已经聊了多久」的直观感。
    """
    stories = [s for s in project.stories if s.display_text]
    covered = len({s.topic for s in project.stories})
    topic_total = len(TOPIC_ORDER)
    total_chars = sum(len(s.display_text) for s in project.stories)
    audio_count = sum(1 for s in project.stories if s.audio_filename)

    change_total = 0
    for story in project.stories:
        if story.raw_text and story.polished_text and story.raw_text != story.polished_text:
            change_total += build_diff(story.raw_text, story.polished_text)["change_count"]

    return {
        "story_count": len(stories),
        "covered_topics": covered,
        "topic_total": topic_total,
        "percent": round(covered / topic_total * 100) if topic_total else 0,
        "total_chars": total_chars,
        "minutes": max(1, round(total_chars / SPEECH_CHARS_PER_MINUTE)) if total_chars else 0,
        "audio_count": audio_count,
        "change_total": change_total,
    }


def story_views(project: Project) -> list[dict]:
    views = []
    for story in project.stories:
        views.append(
            {
                "story": story,
                "diff": build_diff(story.raw_text, story.polished_text),
                "summary": summarize(story.raw_text, story.polished_text),
                "audio_url": f"/media/audio/{story.audio_filename}" if story.audio_filename else "",
            }
        )
    return views


@router.get("/", response_class=templates.TemplateResponse)
def index(request: Request, db: Session = Depends(get_db)):
    projects = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"projects": projects, "ai_enabled": settings.ai_enabled},
    )


@router.post("/create")
def create_project(
    title: str = Form(""),
    narrator_name: str = Form(...),
    interviewer_name: str = Form(""),
    dedication: str = Form(""),
    db: Session = Depends(get_db),
):
    narrator = narrator_name.strip()
    if not narrator:
        raise HTTPException(status_code=400, detail="请填写讲述者的称呼")

    book_title = title.strip() or f"{narrator}的一生"
    project = Project(
        token=uuid.uuid4().hex[:16],
        title=book_title,
        narrator_name=narrator,
        interviewer_name=interviewer_name.strip(),
        dedication=dedication.strip(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return RedirectResponse(url=f"/project/{project.token}", status_code=303)


@router.get("/project/{token}", response_class=templates.TemplateResponse)
def project_page(request: Request, token: str, db: Session = Depends(get_db)):
    project = find_project(db, token)
    return templates.TemplateResponse(
        request,
        "project.html",
        {
            "project": project,
            "stats": topic_stats(project),
            "metrics": project_metrics(project),
            "views": story_views(project),
            "topics": TOPICS,
            "topic_names": {t.key: t.name for t in TOPICS},
            "ai_enabled": settings.ai_enabled,
        },
    )


@router.get("/interview/{token}", response_class=templates.TemplateResponse)
def interview_page(request: Request, token: str, db: Session = Depends(get_db)):
    project = find_project(db, token)
    return templates.TemplateResponse(
        request,
        "interview.html",
        {
            "project": project,
            "topics": TOPICS,
            "ai_enabled": settings.ai_enabled,
        },
    )


@router.get("/book/{token}", response_class=templates.TemplateResponse)
def book_page(request: Request, token: str, db: Session = Depends(get_db)):
    project = find_project(db, token)
    book = build_book(project)
    return templates.TemplateResponse(
        request,
        "book.html",
        {
            "project": project,
            "book": book,
            "print_mode": request.query_params.get("print") == "1",
            "topic_map": TOPIC_MAP,
        },
    )


@router.get("/book/{token}/pdf")
async def book_pdf(token: str, db: Session = Depends(get_db)):
    project = find_project(db, token)
    if not project.stories:
        raise HTTPException(status_code=400, detail="还没有任何故事，先让长辈讲几句吧")
    try:
        pdf_path = await run_in_threadpool(export_book_pdf, token)
    except PdfError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"memoir-{token}.pdf",
    )
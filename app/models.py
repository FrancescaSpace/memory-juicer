from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    narrator_name: Mapped[str] = mapped_column(String(60))
    interviewer_name: Mapped[str] = mapped_column(String(60), default="")
    dedication: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    stories: Mapped[list["Story"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Story.created_at",
    )
    photos: Mapped[list["Photo"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Photo.sort_index",
    )

    @property
    def story_count(self) -> int:
        return len(self.stories)


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(40), index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    polished_text: Mapped[str] = mapped_column(Text, default="")
    audio_filename: Mapped[str] = mapped_column(String(200), default="")
    provider: Mapped[str] = mapped_column(String(40), default="offline")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="stories")

    @property
    def display_text(self) -> str:
        return (self.polished_text or self.raw_text).strip()


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    caption: Mapped[str] = mapped_column(String(240), default="")
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="photos")
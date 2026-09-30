import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Float, Boolean, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(Text, default="demo")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=True)


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    camera_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    points: Mapped[list] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    camera_id: Mapped[str] = mapped_column(String, index=True)
    camera_name: Mapped[str] = mapped_column(String)
    track_id: Mapped[int]
    kind: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="new", index=True)
    started_at: Mapped[str] = mapped_column(String, index=True)
    ended_at: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    zone_name: Mapped[str] = mapped_column(String, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    snapshot_url: Mapped[str | None] = mapped_column(String, nullable=True)


class Outbox(Base):
    __tablename__ = "event_outbox"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class MediaOutbox(Base):
    __tablename__ = "media_outbox"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    content_type: Mapped[str] = mapped_column(String)


url = os.getenv("DATABASE_URL", "sqlite:///./hse.db")
engine = create_engine(
    url,
    connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
Session = sessionmaker(engine, expire_on_commit=False)


def asdict(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}

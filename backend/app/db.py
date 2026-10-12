from __future__ import annotations
from sqlalchemy import JSON, Boolean, Float, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


class PortfolioRecord(Base):
    __tablename__ = "portfolios"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON)
    app_count: Mapped[float] = mapped_column(Float)


def make_engine(url: str | None = None):
    return create_engine(url or settings.database_url, future=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

from __future__ import annotations
from sqlalchemy.orm import Session
from .db import PortfolioRecord
from .schemas import Portfolio


def save_portfolio(db: Session, portfolio: Portfolio) -> int:
    record = PortfolioRecord(
        name=portfolio.name,
        synthetic=portfolio.synthetic,
        payload=portfolio.model_dump(mode="json"),
        app_count=float(len(portfolio.applications)),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.id


def get_portfolio(db: Session, portfolio_id: int) -> Portfolio | None:
    record = db.get(PortfolioRecord, portfolio_id)
    return Portfolio.model_validate(record.payload) if record else None

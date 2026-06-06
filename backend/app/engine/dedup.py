"""Deduplication: prevents storing the same job twice across sources."""
import hashlib
from sqlalchemy.orm import Session
from ..models import Job
from ..scrapers.base import RawJob


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:64]


def is_duplicate(db: Session, raw: RawJob) -> bool:
    return db.query(Job).filter(Job.url_hash == raw.url_hash).first() is not None

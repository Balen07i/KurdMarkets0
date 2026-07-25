"""AISummary — one generated-and-cached daily market summary.

Generated exactly once per day by the worker (after that day's rates are
verified/published), then served identically to every user by the bot —
never regenerated per-request. Stored in Postgres (not just Redis) so
summaries have permanent history and Redis cache loss is not data loss.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.enums import Language
from core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AISummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_summaries"

    summary_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    language: Mapped[Language] = mapped_column(
        Enum(Language, name="language", native_enum=True), default=Language.CKB, nullable=False
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Version of the prompt template used (see history/prompts/ for the
    # versioned templates themselves), so we can track quality changes
    # over time as the prompt is iterated on.
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)

    # The exact set of PublishedRate IDs the summary was generated from,
    # for auditability ("what data was the AI shown when it wrote this").
    source_rate_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AISummary date={self.summary_date} language={self.language!r}>"

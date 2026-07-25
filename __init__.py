"""ORM models package.

Import every model module here so:
  1. `Base.metadata` is fully populated when Alembic autogenerate runs
     (`alembic/env.py` imports `core.models` for exactly this reason).
  2. Other code can do `from core.models import Asset, PublishedRate, ...`
     instead of reaching into individual submodules.
"""

from core.models.base import Base
from core.models.asset import Asset
from core.models.source import Source
from core.models.raw_reading import RawReading
from core.models.published_rate import PublishedRate
from core.models.user import User
from core.models.alert import Alert
from core.models.ai_summary import AISummary

__all__ = [
    "Base",
    "Asset",
    "Source",
    "RawReading",
    "PublishedRate",
    "User",
    "Alert",
    "AISummary",
]

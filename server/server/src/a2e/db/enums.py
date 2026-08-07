from sqlalchemy.orm import InstrumentedAttribute

from a2e.db import models

__all__ = ["ENUM_COLUMNS"]


ENUM_COLUMNS: set[InstrumentedAttribute[str]] = {
    models.UserRole.name,
}

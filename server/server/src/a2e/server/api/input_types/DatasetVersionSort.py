from enum import Enum

import strawberry

from a2e.server.api.types.SortDir import SortDir


@strawberry.enum
class DatasetVersionColumn(Enum):
    createdAt = "created_at"


@strawberry.input(description="The sort key and direction for dataset version connections")
class DatasetVersionSort:
    col: DatasetVersionColumn
    dir: SortDir

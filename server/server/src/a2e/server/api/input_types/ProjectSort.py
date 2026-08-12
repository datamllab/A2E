from enum import Enum

import strawberry

from a2e.server.api.types.SortDir import SortDir


@strawberry.enum
class ProjectColumn(Enum):
    name = "name"
    endTime = "end_time"


@strawberry.input(description="The sort key and direction for project connections")
class ProjectSort:
    col: ProjectColumn
    dir: SortDir

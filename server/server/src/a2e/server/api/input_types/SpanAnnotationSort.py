from enum import Enum

import strawberry

from a2e.server.api.types.SortDir import SortDir


@strawberry.enum
class SpanAnnotationColumn(Enum):
    createdAt = "created_at"
    name = "name"


@strawberry.input(description="The sort key and direction for SpanAnnotation connections")
class SpanAnnotationSort:
    col: SpanAnnotationColumn
    dir: SortDir

from datetime import datetime
from enum import Enum

import strawberry
from strawberry.scalars import JSON

from a2e.db import models
from a2e.server.api.types.ExampleRevisionInterface import ExampleRevision


@strawberry.enum
class RevisionKind(Enum):
    CREATE = "CREATE"
    PATCH = "PATCH"
    DELETE = "DELETE"


@strawberry.type
class DatasetExampleRevision(ExampleRevision):
    """
    Represents a revision (i.e., update or alteration) of a dataset example.
    """

    revision_kind: RevisionKind
    created_at: datetime

    @classmethod
    def from_orm_revision(cls, revision: models.DatasetExampleRevision) -> "DatasetExampleRevision":
        return cls(
            input=JSON(revision.input),
            output=JSON(revision.output),
            metadata=JSON(revision.metadata_),
            revision_kind=RevisionKind(revision.revision_kind),
            created_at=revision.created_at,
        )

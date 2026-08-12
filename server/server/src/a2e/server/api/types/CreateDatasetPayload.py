import strawberry

from a2e.server.api.types.Dataset import Dataset


@strawberry.type
class CreateDatasetPayload:
    dataset: Dataset

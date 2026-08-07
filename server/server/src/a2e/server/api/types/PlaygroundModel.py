import strawberry
from strawberry.types import Info

from a2e.server.api.context import Context
from a2e.server.api.types.GenerativeProvider import GenerativeProviderKey
from a2e.server.api.types.ModelInterface import ModelInterface


@strawberry.type
class PlaygroundModel(ModelInterface):
    name_value: strawberry.Private[str]
    provider_key_value: strawberry.Private[GenerativeProviderKey]

    @strawberry.field
    async def name(self, info: Info[Context, None]) -> str:
        return self.name_value

    @strawberry.field
    async def provider_key(self, info: Info[Context, None]) -> GenerativeProviderKey:
        return self.provider_key_value

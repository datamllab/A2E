from typing import Optional

import strawberry

from a2e.server.api.types.GenerativeProvider import GenerativeProviderKey


@strawberry.interface
class ModelInterface:
    @strawberry.field
    async def name(self) -> str:
        raise NotImplementedError

    @strawberry.field
    async def provider_key(self) -> Optional[GenerativeProviderKey]:
        raise NotImplementedError

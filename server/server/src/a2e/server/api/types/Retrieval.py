from typing import Optional

import strawberry
from strawberry import ID

from a2e.server.api.interceptor import GqlValueMediator


@strawberry.type
class Retrieval:
    query_id: ID
    document_id: ID
    relevance: Optional[float] = strawberry.field(default=GqlValueMediator())

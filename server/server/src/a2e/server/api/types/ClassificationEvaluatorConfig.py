from typing import Optional

import strawberry
from strawberry.scalars import JSON

from a2e.db.types.annotation_configs import OptimizationDirection
from a2e.server.api.types.PromptVersionTemplate import PromptMessage


@strawberry.type
class ClassificationEvaluatorConfig:
    name: str
    description: Optional[str] = None
    optimization_direction: OptimizationDirection
    messages: list[PromptMessage]
    choices: JSON

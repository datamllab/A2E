import strawberry
from strawberry.scalars import JSON

from a2e.db.types.prompts import PromptTemplateFormat


@strawberry.input
class PromptTemplateOptions:
    variables: JSON
    format: PromptTemplateFormat

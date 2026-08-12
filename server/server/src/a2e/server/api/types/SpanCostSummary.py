import strawberry

from a2e.server.api.types.CostBreakdown import CostBreakdown


@strawberry.type
class SpanCostSummary:
    prompt: CostBreakdown = strawberry.field(default_factory=CostBreakdown)
    completion: CostBreakdown = strawberry.field(default_factory=CostBreakdown)
    total: CostBreakdown = strawberry.field(default_factory=CostBreakdown)

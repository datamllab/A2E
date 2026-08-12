import strawberry

from a2e.server.api.mutations.annotation_config_mutations import AnnotationConfigMutationMixin
from a2e.server.api.mutations.api_key_mutations import ApiKeyMutationMixin
from a2e.server.api.mutations.chat_mutations import (
    ChatCompletionMutationMixin,
)
from a2e.server.api.mutations.dataset_label_mutations import DatasetLabelMutationMixin
from a2e.server.api.mutations.dataset_mutations import DatasetMutationMixin
from a2e.server.api.mutations.dataset_split_mutations import DatasetSplitMutationMixin
from a2e.server.api.mutations.document_annotations_mutations import (
    DocumentAnnotationMutationMixin,
)
from a2e.server.api.mutations.evaluator_mutations import EvaluatorMutationMixin
from a2e.server.api.mutations.experiment_mutations import ExperimentMutationMixin
from a2e.server.api.mutations.generative_model_custom_provider_mutations import (
    GenerativeModelCustomProviderMutationMixin,
)
from a2e.server.api.mutations.model_mutations import ModelMutationMixin
from a2e.server.api.mutations.project_mutations import ProjectMutationMixin
from a2e.server.api.mutations.project_session_annotations_mutations import (
    ProjectSessionAnnotationMutationMixin,
)
from a2e.server.api.mutations.project_trace_retention_policy_mutations import (
    ProjectTraceRetentionPolicyMutationMixin,
)
from a2e.server.api.mutations.prompt_label_mutations import PromptLabelMutationMixin
from a2e.server.api.mutations.prompt_mutations import PromptMutationMixin
from a2e.server.api.mutations.prompt_version_tag_mutations import PromptVersionTagMutationMixin
from a2e.server.api.mutations.secret_mutations import SecretMutationMixin
from a2e.server.api.mutations.span_annotations_mutations import SpanAnnotationMutationMixin
from a2e.server.api.mutations.trace_annotations_mutations import TraceAnnotationMutationMixin
from a2e.server.api.mutations.trace_mutations import TraceMutationMixin
from a2e.server.api.mutations.user_mutations import UserMutationMixin


@strawberry.type
class Mutation(
    AnnotationConfigMutationMixin,
    ApiKeyMutationMixin,
    ChatCompletionMutationMixin,
    DatasetLabelMutationMixin,
    DatasetMutationMixin,
    DatasetSplitMutationMixin,
    DocumentAnnotationMutationMixin,
    EvaluatorMutationMixin,
    ExperimentMutationMixin,
    GenerativeModelCustomProviderMutationMixin,
    ModelMutationMixin,
    ProjectMutationMixin,
    ProjectTraceRetentionPolicyMutationMixin,
    PromptMutationMixin,
    PromptVersionTagMutationMixin,
    PromptLabelMutationMixin,
    SecretMutationMixin,
    SpanAnnotationMutationMixin,
    ProjectSessionAnnotationMutationMixin,
    TraceAnnotationMutationMixin,
    TraceMutationMixin,
    UserMutationMixin,
):
    pass

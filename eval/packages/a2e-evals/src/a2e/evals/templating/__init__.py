"""
Templating module - DEPRECATED

This module has been moved to a2e.evals.llm.prompts.
All imports from this module will continue to work but will issue deprecation warnings.

Please update your imports to use a2e.evals.llm.prompts instead.
"""

import warnings

# Re-export everything from the new location for backward compatibility
from a2e.evals.llm.prompts import (
    FormatterFactory,
    FStringFormatter,
    MustacheFormatter,
    Template,
    TemplateFormat,
    TemplateFormatter,
    detect_template_format,
)

# Issue deprecation warning when module is imported
warnings.warn(
    "The a2e.evals.templating module is deprecated and will be removed in a future version. "
    "Please use a2e.evals.llm.prompts instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "FormatterFactory",
    "FStringFormatter",
    "MustacheFormatter",
    "Template",
    "TemplateFormat",
    "TemplateFormatter",
    "detect_template_format",
]

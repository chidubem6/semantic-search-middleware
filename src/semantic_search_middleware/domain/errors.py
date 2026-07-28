"""Domain-level exception types.

Errors that belong to the core rather than any adapter, so inner layers can
raise them and outer layers (the API) can catch them without depending on an
adapter package. Keeps the hexagonal rule intact: dependencies point inward.
"""


class LlmError(RuntimeError):
    """The language model could not be reached or returned an unusable response.

    Defined in the domain (not in `llm/`) so the API layer can catch it without
    importing an adapter. The rule holds: arrows point inward.
    """

class LlmError(RuntimeError):
    """The language model could not be reached or returned an unusable response.

    Defined in the domain (not in `llm/`) so the API layer can catch it without
    importing an adapter. The rule holds: arrows point inward.
    """

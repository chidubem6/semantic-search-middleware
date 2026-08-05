from typing import Literal

import pytest
from pydantic import ValidationError

from semantic_search_middleware.config import Settings


def test_validation_fails_for_invalid_strategy() -> None:
    with pytest.raises(ValidationError):
        Settings(index_strategy="invalid_strategy")


@pytest.mark.parametrize("strategy", ["isolated", "joined"])
def test_validation_passes_for_valid_strategy(strategy: Literal["isolated", "joined"]) -> None:
    settings = Settings(index_strategy=strategy)
    assert settings.index_strategy == strategy

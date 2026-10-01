import pytest
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

import app.config.rate_limiter as rate_limiter_module


@pytest.fixture(autouse=True)
def use_memory_storage_for_rate_limiter():
    """
    Swap the global rate limiter's Redis storage with in-memory storage for
    all unit tests. This prevents tests from requiring a live Redis connection.
    Rate limit counts are reset per test via a fresh MemoryStorage instance.
    """
    memory_storage = MemoryStorage()
    original_storage = rate_limiter_module.limiter._storage
    original_limiter = rate_limiter_module.limiter._limiter

    rate_limiter_module.limiter._storage = memory_storage
    rate_limiter_module.limiter._limiter = FixedWindowRateLimiter(memory_storage)

    yield

    rate_limiter_module.limiter._storage = original_storage
    rate_limiter_module.limiter._limiter = original_limiter

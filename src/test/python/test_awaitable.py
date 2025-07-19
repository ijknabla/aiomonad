import pytest
from aiomonad import pure


@pytest.mark.parametrize("i", [-1, 0, +1])
@pytest.mark.asyncio
async def test_await_pure(i: int):
    assert await pure(i) == i

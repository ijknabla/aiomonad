import pytest
from aiomonad import pure


async def async_double(i: int) -> int:
    return i * 2


@pytest.mark.parametrize("i", [-1, 0, +1])
@pytest.mark.asyncio
async def test_await_pure(i: int):
    assert await pure(i) == i
    assert await (pure(i) * async_double) == i * 2
    assert await (pure(i) * async_double * async_double) == i * 4

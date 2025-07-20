import pytest
from aiomonad import end, foreach, pure


def double(i: int) -> int:
    return i * 2


async def async_double(i: int) -> int:
    return i * 2


@pytest.mark.parametrize("i", [-1, 0, +1])
@pytest.mark.asyncio
async def test_await_pure(i: int) -> None:
    assert await pure(i) == i
    assert await (pure(i) * async_double) == i * 2
    assert await (pure(i) * async_double * async_double) == i * 4

    assert await (pure(i) / double) == i * 2
    assert await (pure(i) / double / double) == i * 4


@pytest.mark.asyncio
async def test_foreach() -> None:
    assert await (foreach(range(10)) % end) == tuple(range(10))

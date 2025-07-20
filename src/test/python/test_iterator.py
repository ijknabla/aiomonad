import pytest
from aiomonad import end, foreach


@pytest.mark.asyncio
async def test_foreach() -> None:
    assert await (foreach(range(10)) % end) == tuple(range(10))

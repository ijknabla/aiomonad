from __future__ import annotations

__all__ = [
    "pure",
]

import enum
from collections.abc import Awaitable, Generator
from typing import Any, Final, TypeVar, final

T = TypeVar("T")


@final
class Pure(enum.Enum):
    instance = enum.auto()

    def __call__(self, x: T) -> AwaitableMonad[T]:
        async def awaitable() -> T:
            return x

        return AwaitableMonad(awaitable())


class AwaitableMonad(Awaitable[T]):
    def __init__(self, awaitable: Awaitable[T]) -> None:
        self.__awaitable = awaitable

    def __await__(self) -> Generator[Any, Any, T]:
        return self.__awaitable.__await__()


pure: Final = Pure.instance

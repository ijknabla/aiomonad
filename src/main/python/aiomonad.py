from __future__ import annotations

__all__ = [
    "pure",
    "foreach",
    "end",
]

import enum
from collections.abc import (
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Iterable,
)
from typing import TYPE_CHECKING, Any, Final, TypeVar, final

if TYPE_CHECKING:
    from typing_extensions import Self

T = TypeVar("T")
U = TypeVar("U")


@final
class Pure(enum.Enum):
    instance = enum.auto()

    def __call__(self, x: T) -> AwaitableMonad[T]:
        async def awaitable() -> T:
            return x

        return AwaitableMonad(awaitable())


@final
class Foreach(enum.Enum):
    instance = enum.auto()

    def __call__(
        self, iterable: Iterable[T] | AsyncIterable[T]
    ) -> AsyncIteratorMonad[T]:
        if isinstance(iterable, AsyncIterable):
            return AsyncIteratorMonad(iterable.__aiter__())

        async def iterator() -> AsyncIterator[T]:
            for x in iterable:
                yield x

        return AsyncIteratorMonad(iterator())


@final
class End(enum.Enum):
    instance = enum.auto()


@final
class AwaitableMonad(Awaitable[T]):
    def __init__(self, awaitable: Awaitable[T]) -> None:
        self.__awaitable = awaitable

    def __await__(self) -> Generator[Any, Any, T]:
        return self.__awaitable.__await__()

    def bind(self, f: Callable[[T], Awaitable[U]]) -> AwaitableMonad[U]:
        async def bind() -> U:
            return await f(await self)

        return AwaitableMonad(bind())

    __mul__ = bind

    def map(self, f: Callable[[T], U]) -> AwaitableMonad[U]:
        async def bind() -> U:
            return f(await self)

        return AwaitableMonad(bind())

    __truediv__ = map


@final
class AsyncIteratorMonad(AsyncIterator[T]):
    def __init__(self, iterator: AsyncIterator[T]) -> None:
        self.__iterator = iterator

    def __aiter__(self) -> Self:
        return self

    def __anext__(self) -> Awaitable[T]:
        return self.__iterator.__anext__()

    def end(self) -> AwaitableMonad[tuple[T, ...]]:
        async def end() -> tuple[T, ...]:
            return tuple([x async for x in self])

        return AwaitableMonad(end())

    def bind(self, f: Callable[[T], AsyncIterable[U]]) -> AsyncIteratorMonad[U]:
        async def bind() -> AsyncIterator[U]:
            async for x in self:
                async for y in f(x):
                    yield y

        return AsyncIteratorMonad(bind())

    __mul__ = bind

    def map(self, f: Callable[[T], U]) -> AsyncIteratorMonad[U]:
        async def map() -> AsyncIterator[U]:
            async for x in self:
                yield f(x)

        return AsyncIteratorMonad(map())

    def __mod__(self, operation: End) -> AwaitableMonad[tuple[T, ...]]:
        return self.end()


pure: Final = Pure.instance
foreach: Final = Foreach.instance
end: Final = End.instance

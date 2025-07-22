from __future__ import annotations

__all__ = [
    "pure",
    "do",
    "foreach",
    "using",
    "end",
    "tap",
]

import enum
from collections.abc import (
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    Generator,
    Iterable,
)
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    asynccontextmanager,
)
from functools import wraps
from types import TracebackType
from typing import TYPE_CHECKING, Any, Final, TypeVar, Union, final, overload

if TYPE_CHECKING:
    from typing_extensions import TypeAlias
else:
    TypeAlias = ...


T = TypeVar("T")
U = TypeVar("U")


AsyncIterableLike: TypeAlias = Union[Iterable[T], AsyncIterable[T]]
AsyncContextManagerLike: TypeAlias = Union[
    AbstractContextManager[T], AbstractAsyncContextManager[T]
]


@final
class Pure(enum.Enum):
    instance = enum.auto()

    def lift(self, x: T) -> AwaitableMonad[T]:
        async def awaitable() -> T:
            return x

        return AwaitableMonad(awaitable())

    __call__ = lift

    def fun(self, f: Callable[[T], U]) -> Callable[[T], AwaitableMonad[U]]:
        @wraps(f)
        def wrapped(x: T, /) -> AwaitableMonad[U]:
            return self.lift(f(x))

        return wrapped

    __getitem__ = fun


@final
class Do(enum.Enum):
    instance = enum.auto()

    def lift(self, awaitable: Awaitable[T]) -> AwaitableMonad[T]:
        if isinstance(awaitable, AwaitableMonad):
            return awaitable

        return AwaitableMonad(awaitable)

    __call__ = lift

    def fun(self, f: Callable[[T], Awaitable[U]]) -> Callable[[T], AwaitableMonad[U]]:
        @wraps(f)
        def wrapped(x: T, /) -> AwaitableMonad[U]:
            return self(f(x))

        return wrapped

    __getitem__ = fun


@final
class Foreach(enum.Enum):
    instance = enum.auto()

    def lift(self, iterable: AsyncIterableLike[T]) -> AsyncIteratorMonad[T]:
        if isinstance(iterable, AsyncIteratorMonad):
            return iterable
        elif isinstance(iterable, AsyncIterable):
            return AsyncIteratorMonad(iterable.__aiter__())

        async def async_iterator() -> AsyncIterator[T]:
            for x in iterable:
                yield x

        return AsyncIteratorMonad(async_iterator())

    __call__ = lift

    def fun(
        self,
        f: Callable[[T], AsyncIterableLike[U]]
        | Callable[[T], Awaitable[AsyncIterableLike[U]]],
    ) -> Callable[[T], AsyncIteratorMonad[U]]:
        async def async_iterator(x: T, /) -> AsyncIterator[U]:
            ys = f(x)
            if isinstance(ys, Awaitable):
                ys = await ys

            async for y in self.lift(ys):
                yield y

        @wraps(f)
        def wrapped(x: T, /) -> AsyncIteratorMonad[U]:
            return AsyncIteratorMonad(async_iterator(x))

        return wrapped

    __getitem__ = fun


@final
class Using(enum.Enum):
    instance = enum.auto()

    def lift(
        self,
        context_manager: AsyncContextManagerLike[T],
    ) -> AsyncContextManagerMonad[T]:
        if isinstance(context_manager, AsyncContextManagerMonad):
            return context_manager
        elif isinstance(context_manager, AbstractAsyncContextManager):
            return AsyncContextManagerMonad(context_manager)

        @asynccontextmanager
        async def async_context_manager() -> AsyncIterator[T]:
            with context_manager as x:
                yield x

        return AsyncContextManagerMonad(async_context_manager())

    __call__ = lift

    def fun(
        self,
        f: Callable[[T], AsyncContextManagerLike[U]]
        | Callable[[T], Awaitable[AsyncContextManagerLike[U]]],
    ) -> Callable[[T], AsyncContextManagerMonad[U]]:
        @asynccontextmanager
        async def async_context_manager(x: T, /) -> AsyncIterator[U]:
            context = f(x)
            if isinstance(context, Awaitable):
                context = await context

            async with self.lift(context) as y:
                yield y

        @wraps(f)
        def wrapped(x: T, /) -> AsyncContextManagerMonad[U]:
            return AsyncContextManagerMonad(async_context_manager(x))

        return wrapped

    __getitem__ = fun


@final
class Tap(enum.Enum):
    instance = enum.auto()


@final
class End(enum.Enum):
    instance = enum.auto()


class BasicAwaitable(Awaitable[T]):
    def __init__(self, awaitable: Awaitable[T]) -> None:
        self._awaitable = awaitable

    def __await__(self) -> Generator[Any, Any, T]:
        return self._awaitable.__await__()


@final
class AwaitableMonad(BasicAwaitable[T]):
    def tap(self) -> TappedAwaitable[T]:
        return TappedAwaitable(self._awaitable)

    def __mod__(self, operation: Tap) -> TappedAwaitable[T]:
        if operation is tap:
            return self.tap()

    def bind(self, f: Callable[[T], Awaitable[U]]) -> AwaitableMonad[U]:
        async def bind() -> U:
            return await f(await self)

        return AwaitableMonad(bind())

    __mul__ = bind

    def pipe(self, f: Callable[[Awaitable[T]], Awaitable[U]]) -> AwaitableMonad[U]:
        return AwaitableMonad(f(self))

    __matmul__ = pipe

    def map(self, f: Callable[[T], U]) -> AwaitableMonad[U]:
        async def bind() -> U:
            return f(await self)

        return AwaitableMonad(bind())

    __truediv__ = map

    __floordiv__ = map_async = bind


@final
class TappedAwaitable(BasicAwaitable[T]):
    def map(self, f: Callable[[T], U]) -> AwaitableMonad[T]:
        async def bind() -> T:
            f(x := await self)
            return x

        return AwaitableMonad(bind())

    __truediv__ = map

    def map_async(self, f: Callable[[T], Awaitable[U]]) -> AwaitableMonad[T]:
        async def map_async() -> T:
            await f(x := await self)
            return x

        return AwaitableMonad(map_async())

    __floordiv__ = map_async


class BasicAsyncIterator(AsyncIterator[T]):
    def __init__(self, iterator: AsyncIterator[T]) -> None:
        self._iterator = iterator

    def __anext__(self) -> Awaitable[T]:
        return self._iterator.__anext__()


@final
class AsyncIteratorMonad(BasicAsyncIterator[T]):
    def tap(self) -> TappedAsyncIterator[T]:
        return TappedAsyncIterator(self._iterator)

    def end(self) -> AwaitableMonad[tuple[T, ...]]:
        async def end() -> tuple[T, ...]:
            return tuple([x async for x in self])

        return AwaitableMonad(end())

    @overload
    def __mod__(self, operation: Tap) -> TappedAsyncIterator[T]: ...

    @overload
    def __mod__(self, operation: End) -> AwaitableMonad[tuple[T, ...]]: ...

    def __mod__(
        self, operation: Tap | End
    ) -> TappedAsyncIterator[T] | AwaitableMonad[tuple[T, ...]]:
        if operation is tap:
            return self.tap()
        elif operation is end:
            return self.end()

    def bind(self, f: Callable[[T], AsyncIterable[U]]) -> AsyncIteratorMonad[U]:
        async def bind() -> AsyncIterator[U]:
            async for x in self:
                async for y in f(x):
                    yield y

        return AsyncIteratorMonad(bind())

    __mul__ = bind

    def pipe(
        self, f: Callable[[AsyncIterable[T]], AsyncIterator[U]]
    ) -> AsyncIteratorMonad[U]:
        return AsyncIteratorMonad(f(self))

    __matmul__ = pipe

    def map(self, f: Callable[[T], U]) -> AsyncIteratorMonad[U]:
        async def map() -> AsyncIterator[U]:
            async for x in self:
                yield f(x)

        return AsyncIteratorMonad(map())

    __truediv__ = map

    def map_async(self, f: Callable[[T], Awaitable[U]]) -> AsyncIteratorMonad[U]:
        async def map_async() -> AsyncIterator[U]:
            async for x in self:
                yield await f(x)

        return AsyncIteratorMonad(map_async())

    __floordiv__ = map_async


@final
class TappedAsyncIterator(BasicAsyncIterator[T]):
    def map(self, f: Callable[[T], U]) -> AsyncIteratorMonad[T]:
        async def map() -> AsyncIterator[T]:
            async for x in self:
                f(x)
                yield x

        return AsyncIteratorMonad(map())

    __truediv__ = map

    def map_async(self, f: Callable[[T], Awaitable[U]]) -> AsyncIteratorMonad[T]:
        async def map_async() -> AsyncIterator[T]:
            async for x in self:
                await f(x)
                yield x

        return AsyncIteratorMonad(map_async())

    __floordiv__ = map_async


class BasicAsyncContextManager(AbstractAsyncContextManager[T]):
    def __init__(self, context_manager: AbstractAsyncContextManager[T]) -> None:
        self._context_manager = context_manager

    def __aenter__(self) -> Coroutine[Any, Any, T]:
        return self._context_manager.__aenter__()

    def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Coroutine[Any, Any, bool | None]:
        return self._context_manager.__aexit__(exc_type, exc_value, traceback)


class AsyncContextManagerMonad(BasicAsyncContextManager[T]):
    def tap(self) -> TappedAsyncContextManager[T]:
        return TappedAsyncContextManager(self._context_manager)

    def end(self) -> AwaitableMonad[T]:
        async def end() -> T:
            async with self as x:
                return x

        return AwaitableMonad(end())

    @overload
    def __mod__(self, operation: Tap) -> TappedAsyncContextManager[T]: ...

    @overload
    def __mod__(self, operation: End) -> AwaitableMonad[T]: ...

    def __mod__(
        self, operation: Tap | End
    ) -> TappedAsyncContextManager[T] | AwaitableMonad[T]:
        if operation is tap:
            return self.tap()
        elif operation is end:
            return self.end()

    def bind(
        self, f: Callable[[T], AbstractAsyncContextManager[U]]
    ) -> AsyncContextManagerMonad[U]:
        @asynccontextmanager
        async def bind() -> AsyncIterator[U]:
            async with self as x:
                async with f(x) as y:
                    yield y

        return AsyncContextManagerMonad(bind())

    __mul__ = bind

    def pipe(
        self,
        f: Callable[[AbstractAsyncContextManager[T]], AbstractAsyncContextManager[U]],
    ) -> AsyncContextManagerMonad[U]:
        return AsyncContextManagerMonad(f(self))

    __matmul__ = pipe

    def map(self, f: Callable[[T], U]) -> AsyncContextManagerMonad[U]:
        @asynccontextmanager
        async def map() -> AsyncIterator[U]:
            async with self as x:
                yield f(x)

        return AsyncContextManagerMonad(map())

    __truediv__ = map

    def map_async(self, f: Callable[[T], Awaitable[U]]) -> AsyncContextManagerMonad[U]:
        @asynccontextmanager
        async def map_async() -> AsyncIterator[U]:
            async with self as x:
                yield await f(x)

        return AsyncContextManagerMonad(map_async())

    __floordiv__ = map_async


class TappedAsyncContextManager(BasicAsyncContextManager[T]):
    def map(self, f: Callable[[T], U]) -> AsyncContextManagerMonad[T]:
        @asynccontextmanager
        async def map() -> AsyncIterator[T]:
            async with self as x:
                f(x)
                yield x

        return AsyncContextManagerMonad(map())

    __truediv__ = map

    def map_async(self, f: Callable[[T], Awaitable[U]]) -> AsyncContextManagerMonad[T]:
        @asynccontextmanager
        async def map_async() -> AsyncIterator[T]:
            async with self as x:
                await f(x)
                yield x

        return AsyncContextManagerMonad(map_async())

    __floordiv__ = map_async


pure: Final = Pure.instance
do: Final = Do.instance
foreach: Final = Foreach.instance
using: Final = Using.instance
end: Final = End.instance
tap: Final = Tap.instance

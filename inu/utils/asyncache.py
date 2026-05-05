"""
Helpers to use [cachetools](https://github.com/tkem/cachetools) with
asyncio.
"""
import asyncio
import functools
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from typing import Any, Callable, MutableMapping, Optional, TypeVar, cast
import inspect
from cachetools import keys


__all__ = ["cached"]


_KT = TypeVar("_KT")
_F = TypeVar("_F", bound=Callable[..., Any])

# Type for a function returning the same type as the one it received.
IdentityFunction = Callable[[_F], _F]


class NullContext:
    """A class for noop context managers."""

    def __enter__(self):
        """Return ``self`` upon entering the runtime context."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Raise any exception triggered within the runtime context."""
        return None

    async def __aenter__(self):
        """Return ``self`` upon entering the runtime context."""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Raise any exception triggered within the runtime context."""
        return None


def cached(
    cache: Optional[MutableMapping[_KT, Any]],
    # ignoring the mypy error to be consistent with the type used
    # in https://github.com/python/typeshed/tree/master/stubs/cachetools
    key: Callable[..., _KT] = keys.hashkey,  # type:ignore
    lock: Optional[
        "AbstractContextManager[Any] | AbstractAsyncContextManager[Any]"
    ] = None,
) -> IdentityFunction:
    """
    Decorator to wrap a function or a coroutine with a memoizing callable
    that saves results in a cache.

    When ``lock`` is provided for a standard function, it's expected to
    implement ``__enter__`` and ``__exit__`` that will be used to lock
    the cache when gets updated. If it wraps a coroutine, ``lock``
    must implement ``__aenter__`` and ``__aexit__``.
    """
    lock = lock or NullContext()

    def decorator(func):
        if inspect.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                if cache is None:
                    return await func(*args, **kwargs)
                
                k = key(*args, **kwargs)
                try:
                    async with cast(AbstractAsyncContextManager[Any], lock):
                        return cache[k]

                except KeyError:
                    pass  # key not found

                val = await func(*args, **kwargs)

                try:
                    async with cast(AbstractAsyncContextManager[Any], lock):
                        cache[k] = val

                except ValueError:
                    pass  # val too large

                return val

            wrapper = async_wrapper

        else:

            def sync_wrapper(*args, **kwargs):
                if cache is None:
                    return func(*args, **kwargs)

                k = key(*args, **kwargs)
                try:
                    with cast(AbstractContextManager[Any], lock):
                        return cache[k]

                except KeyError:
                    pass  # key not found

                val = func(*args, **kwargs)

                try:
                    with cast(AbstractContextManager[Any], lock):
                        cache[k] = val

                except ValueError:
                    pass  # val too large

                return val

            wrapper = sync_wrapper

        return functools.wraps(func)(wrapper)

    return decorator


def cachedmethod(
    cache: Callable[[Any], Optional[MutableMapping[_KT, Any]]],
    # ignoring the mypy error to be consistent with the type used
    # in https://github.com/python/typeshed/tree/master/stubs/cachetools
    key: Callable[..., _KT] = keys.hashkey,  # type:ignore
    lock: Optional[
        Callable[[Any], "AbstractContextManager[Any] | AbstractAsyncContextManager[Any]"]
    ] = None,
) -> IdentityFunction:
    """Decorator to wrap a class or instance method with a memoizing
    callable that saves results in a cache. This works similarly to
    `cached`, but the arguments `cache` and `lock` are callables that
    return the cache object and the lock respectively.
    """
    lock = lock or (lambda _: NullContext())

    def decorator(method):
        if asyncio.iscoroutinefunction(method):

            async def async_wrapper(self, *args, **kwargs):
                method_cache = cache(self)
                if method_cache is None:
                    return await method(self, *args, **kwargs)

                k = key(self, *args, **kwargs)
                try:
                    async with cast(AbstractAsyncContextManager[Any], lock(self)):
                        return method_cache[k]

                except KeyError:
                    pass  # key not found

                val = await method(self, *args, **kwargs)

                try:
                    async with cast(AbstractAsyncContextManager[Any], lock(self)):
                        method_cache[k] = val

                except ValueError:
                    pass  # val too large

                return val

            wrapper = async_wrapper

        else:

            def sync_wrapper(self, *args, **kwargs):
                method_cache = cache(self)
                if method_cache is None:
                    return method(self, *args, **kwargs)

                k = key(self, *args, **kwargs)
                try:
                    with cast(AbstractContextManager[Any], lock(self)):
                        return method_cache[k]

                except KeyError:
                    pass  # key not found

                val = method(self, *args, **kwargs)

                try:
                    with cast(AbstractContextManager[Any], lock(self)):
                        method_cache[k] = val

                except ValueError:
                    pass  # val too large

                return val

            wrapper = sync_wrapper

        return functools.wraps(method)(wrapper)

    return decorator
# ============================================================
# Lightweight TTL cache used to replace Streamlit's st.cache_data
# in a plain FastAPI/async context. Keyed on the function's
# arguments (must be hashable), same TTL semantics as before.
# ============================================================

import time
import functools
import asyncio


def async_ttl_cache(ttl_seconds: int = 3600, maxsize: int = 256):
    def decorator(func):
        store: dict = {}
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            async with lock:
                cached = store.get(key)
                if cached and (now - cached[0]) < ttl_seconds:
                    return cached[1]
            result = await func(*args, **kwargs)
            async with lock:
                if len(store) >= maxsize:
                    # drop oldest entry
                    oldest_key = min(store, key=lambda k: store[k][0])
                    store.pop(oldest_key, None)
                store[key] = (now, result)
            return result

        return wrapper

    return decorator

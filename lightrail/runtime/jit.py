"""
Stage 6: Just-in-Time (JIT) Compilation Runtime
=================================================
Provides the JIT path used by @lightrail.jit decorated functions.

Workflow:
  1. On first call, the decorator triggers the full 6-stage pipeline and
     caches the resulting .lrbs bytecode in a per-function cache keyed by
     argument shapes and dtypes.
  2. Subsequent calls with the same signature hit the cache and dispatch
     the pre-compiled .lrbs directly to the Fabric OS (< 200 ns overhead).
  3. If argument shapes change, the cache is invalidated and re-compilation
     is triggered transparently.

JIT cache key = (function_qualname, tuple(arg_shapes), tuple(arg_dtypes))

The LightRail JIT is simpler than CUDA's NVRTC because:
  - No warp configuration to tune: channel assignments are static.
  - No occupancy calculation: optical channels never "block" each other.
  - Deterministic compilation: same input always yields identical bytecode.
"""

from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from lightrail.codegen.bytecode import BytecodeEmitter, LRBS_FLAGS_JIT
from lightrail.ir.ssa import Module
from lightrail.runtime.fabric_os import (
    KernelDescriptor, GlobalScheduler, get_default_scheduler, KernelState
)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    lrbs_bytes:     bytes
    descriptor:     KernelDescriptor
    compile_time_s: float
    hit_count:      int = 0


class JITCache:
    """Thread-safe (GIL-protected) in-process compilation cache."""

    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}

    def key(self, fn_name: str, args: Tuple) -> str:
        shapes_dtypes = repr([(getattr(a, "shape", type(a).__name__),
                               getattr(a, "dtype", type(a).__name__)) for a in args])
        raw = f"{fn_name}:{shapes_dtypes}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, key: str) -> Optional[CacheEntry]:
        entry = self._store.get(key)
        if entry:
            entry.hit_count += 1
        return entry

    def put(self, key: str, entry: CacheEntry) -> None:
        self._store[key] = entry

    def invalidate(self, fn_name: str) -> int:
        """Remove all cache entries for a given function name."""
        prefix = hashlib.sha256(fn_name.encode()).hexdigest()[:4]
        removed = [k for k in self._store if k.startswith(prefix)]
        for k in removed:
            del self._store[k]
        return len(removed)

    def stats(self) -> Dict[str, Any]:
        total_hits = sum(e.hit_count for e in self._store.values())
        return {
            "cached_kernels": len(self._store),
            "total_hits":     total_hits,
        }


_GLOBAL_CACHE = JITCache()


# ---------------------------------------------------------------------------
# JIT Runner
# ---------------------------------------------------------------------------

class JITRunner:
    """
    Wraps a compiled Module and handles cache lookup + dispatch.
    """

    def __init__(
        self,
        fn_name:   str,
        compile_fn: Callable[[Tuple], Module],
        scheduler:  Optional[GlobalScheduler] = None,
    ) -> None:
        self.fn_name    = fn_name
        self.compile_fn = compile_fn   # called with (args,) -> Module
        self.scheduler  = scheduler or get_default_scheduler()
        self.cache      = _GLOBAL_CACHE

    def __call__(self, *args: Any) -> Any:
        cache_key = self.cache.key(self.fn_name, args)
        entry = self.cache.get(cache_key)

        if entry is None:
            entry = self._compile_and_cache(args, cache_key)

        descriptor = KernelDescriptor(
            name=self.fn_name,
            lrbs_bytes=entry.lrbs_bytes,
            args=list(args),
            fabric_generation=1,
        )

        result_descriptor = self.scheduler.dispatch(descriptor)
        if result_descriptor.state == KernelState.FAILED:
            raise RuntimeError(f"JIT kernel '{self.fn_name}' failed during execution.")

        return result_descriptor

    def _compile_and_cache(self, args: Tuple, cache_key: str) -> CacheEntry:
        t0 = time.perf_counter()
        module = self.compile_fn(args)
        emitter = BytecodeEmitter()
        lrbs = emitter.emit(module, flags=LRBS_FLAGS_JIT)
        compile_time = time.perf_counter() - t0

        descriptor = KernelDescriptor(
            name=self.fn_name,
            lrbs_bytes=lrbs,
            num_tiles=module.device_functions()[0].attrs.get("num_tiles", 1)
                      if module.device_functions() else 1,
            fabric_generation=1,
        )

        entry = CacheEntry(
            lrbs_bytes=lrbs,
            descriptor=descriptor,
            compile_time_s=compile_time,
        )
        self.cache.put(cache_key, entry)
        return entry

    def clear_cache(self) -> None:
        self.cache.invalidate(self.fn_name)

    def cache_info(self) -> Dict[str, Any]:
        return self.cache.stats()

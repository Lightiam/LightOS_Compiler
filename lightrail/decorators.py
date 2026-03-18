"""
@lightrail.jit Decorator
========================
Primary developer-facing API.  Wraps a Python function with LightRail
JIT compilation, mirroring the ergonomics of @torch.jit.script or
@jax.jit but targeting the LightRail Photonic NCE.

Usage:
    import lightrail

    @lightrail.jit
    def my_kernel(A: "float32", B: "float32", N: "int32") -> "float32":
        acc: float32 = 0.0
        for i in range(N):
            acc += A[i] * B[i]
        return acc

    # First call: compiles to .lrbs and dispatches via Fabric OS
    result = my_kernel(a_buf, b_buf, 1024)

    # Subsequent calls: cache hit, direct dispatch (<200 ns overhead)
    result = my_kernel(a_buf, b_buf, 1024)

Advanced options via @lightrail.jit(mode="aot", num_wdm_channels=32):
    @lightrail.jit(mode="aot")
    def production_kernel(...): ...
"""

from __future__ import annotations
import functools
from typing import Any, Callable, Optional

from lightrail.pipeline import CompilationPipeline, CompileOptions
from lightrail.runtime.jit import JITRunner


class _JITDecorator:
    """Returned by @lightrail.jit when called with keyword arguments."""

    def __init__(self, opts: CompileOptions) -> None:
        self.opts = opts

    def __call__(self, fn: Callable) -> "LightRailKernel":
        return LightRailKernel(fn, self.opts)


class LightRailKernel:
    """
    Wraps a Python function as a LightRail kernel.

    Attributes:
        __wrapped__ : The original Python function (for introspection).
        __lr_opts__ : CompileOptions used for this kernel.
    """

    def __init__(self, fn: Callable, opts: CompileOptions) -> None:
        self.__wrapped__ = fn
        self.__lr_opts__ = opts
        self.__qualname__ = fn.__qualname__
        self.__name__     = fn.__name__
        self.__doc__      = fn.__doc__
        functools.update_wrapper(self, fn)

        self._pipeline = CompilationPipeline(opts)
        self._runner:  Optional[JITRunner] = None
        self._compiled = False

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self._runner is None:
            self._runner = self._pipeline.make_jit_runner(self.__wrapped__)
        return self._runner(*args)

    def compile(self) -> None:
        """Eagerly trigger compilation (useful for benchmarking warm-up)."""
        from lightrail.pipeline import CompilationResult
        result = self._pipeline.compile_function(self.__wrapped__, device=True)
        self._compiled = True
        return result

    def aot_compile(self) -> bytes:
        """
        Compile to AOT binary and return the .lrnpu bytes.
        Useful for offline compilation and deployment.
        """
        aot_opts = CompileOptions(**{
            **self.__lr_opts__.__dict__,
            "mode": "aot",
        })
        pipeline = CompilationPipeline(aot_opts)
        result   = pipeline.compile_function(self.__wrapped__, device=True)
        if result.aot_binary:
            return result.aot_binary.serialise()
        return result.lrbs_bytes

    def cache_info(self) -> dict:
        if self._runner:
            return self._runner.cache_info()
        return {}

    def clear_cache(self) -> None:
        if self._runner:
            self._runner.clear_cache()

    def ir(self) -> str:
        """Return a human-readable dump of the compiled IR."""
        result = self._pipeline.compile_function(self.__wrapped__, device=True)
        return result.module.dump()

    def __repr__(self) -> str:
        status = "compiled" if self._compiled else "not yet compiled"
        return (f"<LightRailKernel '{self.__name__}' "
                f"mode={self.__lr_opts__.mode} {status}>")


def jit(
    fn: Optional[Callable] = None,
    *,
    mode: str = "jit",
    num_wdm_channels: int = 64,
    enable_fma: bool = True,
    enable_loop_split: bool = True,
    enable_ternary: bool = True,
    nce_generation: int = 1,
    debug: bool = False,
) -> Any:
    """
    Decorator to JIT-compile a Python function for the LightRail NCE.

    Can be used as:
        @lightrail.jit
        def kernel(...): ...

    or with options:
        @lightrail.jit(mode="aot", num_wdm_channels=32)
        def kernel(...): ...

    Args:
        mode:              "jit" (default) or "aot" for ahead-of-time.
        num_wdm_channels:  Number of WDM channels (1–64, default 64).
        enable_fma:        Enable fused multiply-add fusion pass.
        enable_loop_split: Enable loop splitting / tile pipelining pass.
        enable_ternary:    Enable ternary/analog encoding pass.
        nce_generation:    Target NCE hardware generation (default 1).
        debug:             Emit debug information in the IR.
    """
    opts = CompileOptions(
        mode=mode,
        num_wdm_channels=num_wdm_channels,
        enable_fma=enable_fma,
        enable_loop_split=enable_loop_split,
        enable_ternary=enable_ternary,
        nce_generation=nce_generation,
        debug=debug,
    )

    if fn is not None:
        # Used as @lightrail.jit without parentheses
        return LightRailKernel(fn, opts)
    else:
        # Used as @lightrail.jit(...) with arguments
        return _JITDecorator(opts)

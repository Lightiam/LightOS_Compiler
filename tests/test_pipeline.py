"""End-to-end integration tests for the full compilation pipeline."""
import pytest

import lightrail
from lightrail.pipeline import CompilationPipeline, CompileOptions
from lightrail.ir.ops import Opcode


# ---------------------------------------------------------------------------
# Compilation pipeline integration
# ---------------------------------------------------------------------------

class TestCompilationPipeline:

    def _compile(self, src, fn_name, **opts_kwargs):
        opts = CompileOptions(**opts_kwargs)
        pipeline = CompilationPipeline(opts)
        return pipeline.compile_source(src, fn_name, device=True)

    def test_simple_function(self):
        src = """
def dot(a, b):
    return a + b
"""
        result = self._compile(src, "dot")
        assert result.module is not None
        assert len(result.lrbs_bytes) > 0

    def test_full_pipeline_matmul(self):
        src = """
def matmul_kernel(A, B):
    return matmul(A, B)
"""
        result = self._compile(src, "matmul_kernel")
        assert result.compile_time_s > 0
        assert result.fat_binary_bytes is not None

    def test_loop_kernel(self):
        src = """
def vector_add(N: "int32"):
    acc: float32 = 0.0
    for i in range(N):
        acc += 1.0
    return acc
"""
        result = self._compile(src, "vector_add")
        fn = result.module.get_function("vector_add")
        assert fn is not None
        # Loop splitting should have created tile markers
        ops = [i.op for i in fn.all_instructions()]
        assert Opcode.LOOP_BEGIN in ops

    def test_stage_timing_collected(self):
        src = """
def f(x):
    return x * 2.0
"""
        result = self._compile(src, "f")
        assert len(result.stage_times) > 0
        for stage, t in result.stage_times.items():
            assert t >= 0.0

    def test_aot_mode(self):
        src = """
def aot_kernel(x, y):
    return x + y
"""
        result = self._compile(src, "aot_kernel", mode="aot")
        assert result.aot_binary is not None
        serialised = result.aot_binary.serialise()
        assert serialised[:4] == b"LNPU"

    def test_disable_fma(self):
        src = """
def f(a, b, c):
    t = a * b
    return t + c
"""
        result = self._compile(src, "f", enable_fma=False)
        # Without FMA fusion, FMUL + FADD should remain separate
        fn = result.module.get_function("f")
        ops = [i.op for i in fn.all_instructions()]
        # FMA should not appear (fma disabled)
        assert Opcode.FMA not in ops

    def test_no_wdm_warp_scheduling(self):
        """Verify deterministic WDM channel assignment replaces thread scheduling."""
        src = """
def parallel_ops(a, b, c, d):
    x = a + b
    y = c + d
    return x + y
"""
        result = self._compile(src, "parallel_ops")
        fn = result.module.get_function("parallel_ops")
        # All instructions should have WDM channel assigned
        for instr in fn.all_instructions():
            if instr.result and instr.op != Opcode.WDM_BIND:
                assert "wdm_channel" in instr.attrs

    def test_all_reduce_routed_to_fabric_os(self):
        src = """
def reduce_kernel(x):
    return all_reduce(x, reduction="sum")
"""
        result = self._compile(src, "reduce_kernel")
        fn = result.module.get_function("reduce_kernel")
        for instr in fn.all_instructions():
            if instr.op == Opcode.ALL_REDUCE:
                assert instr.attrs.get("fabric_os_collective") == "ring_allreduce"

    def test_summary_output(self):
        src = """
def f(x, y):
    return x + y
"""
        result = self._compile(src, "f")
        summary = result.summary()
        assert "Module" in summary
        assert "compile" in summary.lower()


# ---------------------------------------------------------------------------
# @lightrail.jit decorator
# ---------------------------------------------------------------------------

class TestJITDecorator:

    def test_basic_decorator(self):
        @lightrail.jit
        def simple_kernel(a, b):
            return a + b

        assert hasattr(simple_kernel, "__wrapped__")
        assert callable(simple_kernel)

    def test_decorator_with_options(self):
        @lightrail.jit(mode="jit", num_wdm_channels=32)
        def kernel(a, b):
            return a + b

        assert kernel.__lr_opts__.num_wdm_channels == 32

    def test_ir_dump(self):
        @lightrail.jit
        def f(x, y):
            return x + y

        ir_text = f.ir()
        assert "f" in ir_text
        assert "fn" in ir_text

    def test_aot_bytes(self):
        @lightrail.jit
        def g(x):
            return x

        aot_bytes = g.aot_compile()
        assert len(aot_bytes) > 0

    def test_kernel_repr(self):
        @lightrail.jit
        def my_func(x):
            return x

        r = repr(my_func)
        assert "my_func" in r
        assert "LightRailKernel" in r

    def test_cache_info(self):
        @lightrail.jit
        def h(x, y):
            return x + y

        info = h.cache_info()
        assert isinstance(info, dict)


# ---------------------------------------------------------------------------
# Ternary & Analog native type compilation
# ---------------------------------------------------------------------------

class TestPhotographicNativeTypes:

    def test_ternary_kernel(self):
        src = """
def ternary_kernel(a, b):
    return a
"""
        from lightrail.ir.ssa import Module, Builder
        from lightrail.ir.ops import Opcode
        from lightrail.ir.types import FP32

        m = Module(name="ternary_k")
        b = Builder(m)
        fn = b.new_function("ternary_k", [("a", FP32), ("b", FP32)],
                             ret=FP32, is_device=True)
        entry = b.new_block(fn, "entry")
        b.use_block(entry)
        # Emit native ternary dot product
        r = b.emit(Opcode.TDOT, operands=["a", "b"], ty=FP32, result_hint="r")
        b.ret(r)

        pipeline = CompilationPipeline()
        result = pipeline.compile_module(m)
        ops = [i.op for i in result.module.get_function("ternary_k").all_instructions()]
        assert Opcode.TERNARY_ENCODE in ops

    def test_analog_wave_annotation(self):
        from lightrail.ir.ssa import Module, Builder
        from lightrail.ir.ops import Opcode
        from lightrail.ir.types import FP32

        m = Module(name="analog_k")
        b = Builder(m)
        fn = b.new_function("analog_k", [("a", FP32)], ret=FP32, is_device=True)
        entry = b.new_block(fn, "entry")
        b.use_block(entry)
        r = b.emit(Opcode.WAVE_MOD, operands=["a"],
                   ty=FP32, attrs={"weight": 0.5}, result_hint="wmod")
        b.ret(r)

        from lightrail.codegen.ternary import TernaryEncodingPass
        TernaryEncodingPass().run(m)

        fn2 = m.get_function("analog_k")
        for instr in fn2.all_instructions():
            if instr.op == Opcode.WAVE_MOD:
                assert "mzi_phase_rad" in instr.attrs
                assert "layer" in instr.attrs
                assert instr.attrs["layer"] == "analog_6_7"

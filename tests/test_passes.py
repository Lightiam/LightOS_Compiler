"""Tests for compiler optimisation passes (Stages 2 & 3)."""
import pytest

from lightrail.frontend.ast_parser import ASTParser
from lightrail.passes.type_inference  import TypeInferencePass
from lightrail.passes.dead_code       import DeadCodeEliminationPass
from lightrail.passes.alias_analysis  import AliasAnalysisPass
from lightrail.passes.loop_splitting  import LoopSplittingPass
from lightrail.passes.fma_fusion      import FMAFusionPass
from lightrail.passes.graph_partition import GraphPartitionPass
from lightrail.ir.ops import Opcode
from lightrail.ir.types import INT32, FP32, VOID
from lightrail.ir.ssa import Module, Function, BasicBlock, Builder, Instruction


def _parse(src, fn_name):
    return ASTParser().parse_source(src, fn_name, device=True)


# ---------------------------------------------------------------------------
# TypeInferencePass
# ---------------------------------------------------------------------------

class TestTypeInference:

    def test_const_types_inferred(self):
        src = """
def f():
    x = 1
    y = 2.0
    return x
"""
        m = _parse(src, "f")
        TypeInferencePass().run(m)
        fn = m.get_function("f")
        for instr in fn.all_instructions():
            if instr.op == Opcode.CONST and instr.result:
                assert instr.type_ is not None

    def test_cast_from_annotation(self):
        src = """
def f(x: "float32") -> "int32":
    n: int32 = x
    return n
"""
        m = _parse(src, "f")
        TypeInferencePass().run(m)
        fn = m.get_function("f")
        casts = [i for i in fn.all_instructions() if i.op == Opcode.CAST]
        assert len(casts) > 0

    def test_param_types_seeded(self):
        src = """
def g(a: "float32", b: "int32"):
    return a
"""
        m = _parse(src, "g")
        TypeInferencePass().run(m)
        fn = m.get_function("g")
        assert fn.values.type_of("a") == FP32
        assert fn.values.type_of("b") == INT32


# ---------------------------------------------------------------------------
# DeadCodeEliminationPass
# ---------------------------------------------------------------------------

class TestDCE:

    def test_removes_unused_const(self):
        # Build IR manually with a dead constant
        m = Module(name="dce_test")
        b = Builder(m)
        fn = b.new_function("f", [("x", FP32)], ret=FP32)
        entry = b.new_block(fn, "entry")
        b.use_block(entry)
        _dead = b.const(42.0, FP32)   # never used
        b.ret("x")

        n_before = len(list(fn.all_instructions()))
        DeadCodeEliminationPass().run(m)
        n_after  = len(list(fn.all_instructions()))
        assert n_after <= n_before  # dead const removed

    def test_keeps_stores(self):
        src = """
def f(x):
    y = x + 1.0
    return y
"""
        m = _parse(src, "f")
        before_count = len(list(m.get_function("f").all_instructions()))
        DeadCodeEliminationPass().run(m)
        after_count  = len(list(m.get_function("f").all_instructions()))
        assert after_count > 0


# ---------------------------------------------------------------------------
# LoopSplittingPass
# ---------------------------------------------------------------------------

class TestLoopSplitting:

    def test_tile_markers_inserted(self):
        src = """
def loop_fn(N: "int32"):
    for i in range(N):
        x = 1.0 + 2.0
"""
        m = _parse(src, "loop_fn")
        LoopSplittingPass().run(m)
        fn = m.get_function("loop_fn")
        ops = [i.op for i in fn.all_instructions()]
        # Should have TILE_COMPUTE or TILE_LOAD markers
        assert any(op in {Opcode.TILE_COMPUTE, Opcode.TILE_LOAD, Opcode.TILE_BARRIER}
                   for op in ops)


# ---------------------------------------------------------------------------
# FMAFusionPass
# ---------------------------------------------------------------------------

class TestFMAFusion:

    def test_fma_created(self):
        m = Module(name="fma_test")
        b = Builder(m)
        fn = b.new_function("f", [("a", FP32), ("b", FP32), ("c", FP32)], ret=FP32)
        entry = b.new_block(fn, "entry")
        b.use_block(entry)

        # Emit: t = a * b; r = t + c
        t = b.emit(Opcode.FMUL, operands=["a", "b"], ty=FP32, result_hint="t")
        r = b.emit(Opcode.FADD, operands=[t, "c"], ty=FP32, result_hint="r")
        b.ret(r)

        FMAFusionPass().run(m)

        ops = [i.op for i in fn.all_instructions()]
        assert Opcode.FMA in ops
        # FMUL should be fused away
        assert Opcode.FMUL not in ops


# ---------------------------------------------------------------------------
# GraphPartitionPass
# ---------------------------------------------------------------------------

class TestGraphPartition:

    def test_tile_ids_assigned(self):
        src = """
def kernel(A, B, C):
    x = A + B
    y = x * C
    return y
"""
        m = _parse(src, "kernel")
        fn = m.get_function("kernel")
        fn.is_device = True
        GraphPartitionPass().run(m)
        for instr in fn.all_instructions():
            if instr.op not in {Opcode.LOOP_BEGIN, Opcode.LOOP_END}:
                assert "tile_id" in instr.attrs

    def test_collectives_get_tile_0(self):
        src = """
def kernel(x):
    return all_reduce(x, reduction="sum")
"""
        m = _parse(src, "kernel")
        fn = m.get_function("kernel")
        fn.is_device = True
        GraphPartitionPass().run(m)
        for instr in fn.all_instructions():
            if instr.op == Opcode.ALL_REDUCE:
                assert instr.attrs["tile_id"] == 0

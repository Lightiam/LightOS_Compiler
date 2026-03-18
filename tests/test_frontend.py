"""Tests for the LightRail compiler frontend (Stage 1)."""
import pytest

from lightrail.frontend.ast_parser import ASTParser
from lightrail.frontend.host_device_split import HostDeviceSplitter
from lightrail.ir.ops import Opcode
from lightrail.ir.types import FP32, INT32, VOID


# ---------------------------------------------------------------------------
# ASTParser
# ---------------------------------------------------------------------------

class TestASTParser:

    def _parse(self, source: str, fn_name: str):
        return ASTParser().parse_source(source, fn_name, device=True)

    def test_simple_assignment(self):
        src = """
def add(a, b):
    c = a + b
    return c
"""
        module = self._parse(src, "add")
        assert module.name == "add"
        fn = module.get_function("add")
        assert fn is not None

    def test_for_loop(self):
        src = """
def sum_loop(N: "int32") -> "float32":
    acc: float32 = 0.0
    for i in range(N):
        acc += 1.0
    return acc
"""
        module = self._parse(src, "sum_loop")
        fn = module.get_function("sum_loop")
        all_ops = [i.op for i in fn.all_instructions()]
        assert Opcode.LOOP_BEGIN in all_ops

    def test_annotated_types(self):
        src = """
def typed(x: "float32", n: "int32") -> "float32":
    return x
"""
        module = self._parse(src, "typed")
        fn = module.get_function("typed")
        param_types = {name: ty for name, ty in fn.params}
        assert param_types["x"] == FP32
        assert param_types["n"] == INT32

    def test_conditional(self):
        src = """
def cond(a, b):
    if a > b:
        return a
    return b
"""
        module = self._parse(src, "cond")
        fn = module.get_function("cond")
        ops = [i.op for i in fn.all_instructions()]
        assert Opcode.FCMP in ops or Opcode.CBR in ops

    def test_all_reduce_interception(self):
        src = """
def reduce_kernel(x):
    return all_reduce(x, reduction="sum")
"""
        module = self._parse(src, "reduce_kernel")
        fn = module.get_function("reduce_kernel")
        ops = [i.op for i in fn.all_instructions()]
        assert Opcode.ALL_REDUCE in ops

    def test_aug_assign(self):
        src = """
def aug(a, b):
    a += b
    return a
"""
        module = self._parse(src, "aug")
        fn = module.get_function("aug")
        ops = [i.op for i in fn.all_instructions()]
        assert Opcode.FADD in ops

    def test_matmul_call(self):
        src = """
def mm_kernel(A, B):
    return matmul(A, B)
"""
        module = self._parse(src, "mm_kernel")
        fn = module.get_function("mm_kernel")
        ops = [i.op for i in fn.all_instructions()]
        assert Opcode.MATMUL in ops


# ---------------------------------------------------------------------------
# HostDeviceSplitter
# ---------------------------------------------------------------------------

class TestHostDeviceSplitter:

    def test_kernel_suffix_promoted(self):
        src = """
def vector_add_kernel(A, B, C):
    return A
"""
        module = ASTParser().parse_source(src, "vector_add_kernel", device=False)
        # Initially not device
        fn = module.get_function("vector_add_kernel")
        fn.is_device = False
        HostDeviceSplitter().run(module)
        assert module.get_function("vector_add_kernel").is_device

    def test_host_stub_created(self):
        src = """
def my_kernel(A, B):
    return A
"""
        module = ASTParser().parse_source(src, "my_kernel", device=True)
        HostDeviceSplitter().run(module)
        stub = module.get_function("launch_my_kernel")
        assert stub is not None
        assert not stub.is_device

    def test_stub_contains_dispatch(self):
        src = """
def my_kernel(A, B):
    return A
"""
        module = ASTParser().parse_source(src, "my_kernel", device=True)
        HostDeviceSplitter().run(module)
        stub = module.get_function("launch_my_kernel")
        ops = [i.op for i in stub.all_instructions()]
        assert Opcode.NCE_DISPATCH in ops

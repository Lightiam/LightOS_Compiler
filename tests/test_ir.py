"""Tests for the LightRail IR layer (types, ops, SSA)."""
import pytest

from lightrail.ir.types import (
    ScalarType, ScalarKind, VectorType, TensorType, PointerType,
    WavelengthChannelType, TernaryVectorType, AnalogWaveType,
    VOID, BOOL, INT8, INT32, FP8, FP16, BF16, ABFP16, FP32, FP64,
    TERNARY, ANALOG,
    python_type_to_lr, infer_from_annotation,
)
from lightrail.ir.ops import Opcode, Instruction
from lightrail.ir.ssa import BasicBlock, Function, Module, Builder, ValueTable


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class TestTypes:

    def test_scalar_bitwidths(self):
        assert INT32.bitwidth() == 32
        assert FP16.bitwidth()  == 16
        assert FP8.bitwidth()   == 8
        assert TERNARY.bitwidth() == 2
        assert ANALOG.bitwidth()  == 32

    def test_scalar_categories(self):
        assert INT32.is_integer()
        assert FP32.is_float()
        assert TERNARY.is_photonic()
        assert ANALOG.is_photonic()
        assert not INT32.is_photonic()

    def test_vector_bitwidth(self):
        v = VectorType(FP32, 16)
        assert v.bitwidth() == 16 * 32
        assert v.is_numeric()

    def test_tensor_num_elements(self):
        t = TensorType(FP32, (128, 64))
        assert t.num_elements() == 128 * 64
        assert t.bitwidth() == 128 * 64 * 32

    def test_pointer_type(self):
        p = PointerType(FP32, "sram")
        assert p.bitwidth() == 64
        assert "sram" in repr(p)

    def test_wdm_channel_type(self):
        ch = WavelengthChannelType(7)
        assert ch.channel_id == 7
        assert ch.is_photonic()

    def test_python_type_to_lr(self):
        assert python_type_to_lr(float) == FP32
        assert python_type_to_lr(int)   == INT32
        assert python_type_to_lr(bool)  == BOOL

    def test_infer_from_annotation(self):
        assert infer_from_annotation("float32")  == FP32
        assert infer_from_annotation("int32")    == INT32
        assert infer_from_annotation("fp8")      == FP8
        assert infer_from_annotation("abfp16")   == ABFP16
        assert infer_from_annotation("ternary")  == TERNARY
        assert infer_from_annotation("analog")   == ANALOG
        assert infer_from_annotation("void")     == VOID

    def test_type_repr(self):
        assert repr(FP32)    == "fp32"
        assert repr(TERNARY) == "ternary"
        assert repr(VOID)    == "void"


# ---------------------------------------------------------------------------
# ValueTable
# ---------------------------------------------------------------------------

class TestValueTable:

    def test_fresh_unique(self):
        vt = ValueTable()
        a = vt.fresh("x", FP32)
        b = vt.fresh("x", FP32)
        assert a != b
        assert a == "x0"
        assert b == "x1"

    def test_declare_conflict(self):
        vt = ValueTable()
        vt.declare("foo", INT32)
        with pytest.raises(ValueError):
            vt.declare("foo", FP32)

    def test_type_of(self):
        vt = ValueTable()
        vt.declare("bar", FP16)
        assert vt.type_of("bar") == FP16

    def test_unknown_key(self):
        vt = ValueTable()
        with pytest.raises(KeyError):
            vt.type_of("nonexistent")


# ---------------------------------------------------------------------------
# SSA Module / Function / BasicBlock
# ---------------------------------------------------------------------------

class TestSSA:

    def test_module_creation(self):
        m = Module(name="test")
        assert m.name == "test"
        assert m.device_functions() == []
        assert m.host_functions()   == []

    def test_function_add_block(self):
        m = Module(name="test")
        fn = Function(name="f", params=[], ret_type=VOID, is_device=True)
        m.add_function(fn)
        bb = fn.add_block("entry")
        assert fn.entry_block() is bb

    def test_builder_const(self):
        m = Module(name="test")
        b = Builder(m)
        fn = b.new_function("f", [], ret=VOID)
        entry = b.new_block(fn)
        b.use_block(entry)
        c = b.const(3.14, FP32)
        assert c is not None
        assert c in fn.values

    def test_builder_fma(self):
        m = Module(name="test")
        b = Builder(m)
        fn = b.new_function("f", [("x", FP32), ("y", FP32), ("z", FP32)], ret=FP32)
        entry = b.new_block(fn)
        b.use_block(entry)
        result = b.fma("x", "y", "z", FP32)
        assert result is not None
        instr = entry.instructions[-1]
        assert instr.op == Opcode.FMA
        assert instr.operands == ["x", "y", "z"]

    def test_basic_block_terminator(self):
        bb = BasicBlock(label="entry")
        assert not bb.is_terminated()
        bb.append(Instruction(Opcode.RET, None, [], type_=VOID))
        assert bb.is_terminated()

    def test_instruction_purity(self):
        load = Instruction(Opcode.LOAD, "v0", ["ptr"], type_=FP32)
        store = Instruction(Opcode.STORE, None, ["v0", "ptr"], type_=VOID)
        assert load.is_pure()
        assert not store.is_pure()

    def test_module_dump(self):
        m = Module(name="test_mod")
        b = Builder(m)
        fn = b.new_function("kernel", [("a", FP32)], ret=VOID, is_device=True)
        entry = b.new_block(fn)
        b.use_block(entry)
        b.ret()
        dump = m.dump()
        assert "module test_mod" in dump
        assert "kernel" in dump

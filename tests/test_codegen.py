"""Tests for Stage 5: Bytecode & Fat Binary generation."""
import pytest
import struct

from lightrail.frontend.ast_parser import ASTParser
from lightrail.passes.type_inference import TypeInferencePass
from lightrail.passes.graph_partition import GraphPartitionPass
from lightrail.dataflow.wavelength_mapper import WavelengthMapper
from lightrail.dataflow.routing import DataflowRouter
from lightrail.codegen.bytecode import BytecodeEmitter, LRBS_MAGIC, LRBS_FLAGS_JIT
from lightrail.codegen.fat_binary import FatBinaryBundler, FatBinary
from lightrail.codegen.ternary import (
    quantise_to_ternary, ternary_to_float, ternary_dot,
    pack_ternary_word, unpack_ternary_word, mzi_phase_for_weight,
    TernaryEncodingPass,
)
from lightrail.ir.ssa import Module, Builder
from lightrail.ir.types import FP32, VOID


def _full_pipeline(src, fn_name):
    m = ASTParser().parse_source(src, fn_name, device=True)
    TypeInferencePass().run(m)
    fn = m.get_function(fn_name)
    fn.is_device = True
    GraphPartitionPass().run(m)
    WavelengthMapper().run(m)
    DataflowRouter().run(m)
    return m


class TestBytecodeEmitter:

    def test_magic_header(self):
        src = """
def kernel(a, b):
    return a + b
"""
        m = _full_pipeline(src, "kernel")
        emitter = BytecodeEmitter()
        data = emitter.emit(m, flags=LRBS_FLAGS_JIT)
        assert data[:4] == LRBS_MAGIC

    def test_non_empty_output(self):
        src = """
def kernel(a, b, c):
    x = a + b
    y = x * c
    return y
"""
        m = _full_pipeline(src, "kernel")
        emitter = BytecodeEmitter()
        data = emitter.emit(m)
        assert len(data) > 16   # must have more than just a header

    def test_version_bytes(self):
        src = """
def k(a):
    return a
"""
        m = _full_pipeline(src, "k")
        data = BytecodeEmitter().emit(m)
        assert data[4] == 0   # major
        assert data[5] == 1   # minor

    def test_crc_at_end(self):
        """Verify that the last 4 bytes are a valid CRC32."""
        import zlib
        src = """
def k(a):
    return a
"""
        m = _full_pipeline(src, "k")
        data = BytecodeEmitter().emit(m)
        payload = data[:-4]
        stored_crc = struct.unpack(">I", data[-4:])[0]
        computed_crc = zlib.crc32(payload) & 0xFFFFFFFF
        assert stored_crc == computed_crc


class TestFatBinary:

    def test_bundle_and_roundtrip(self):
        host_bytes   = b"host_code_placeholder"
        device_bytes = b"device_lrbs_placeholder"
        bundler = FatBinaryBundler()
        fat = bundler.bundle("myapp", host_bytes, {1: device_bytes})
        assert fat[:4] == b"LRFT"

    def test_deserialise(self):
        host_bytes   = b"host_code"
        device_bytes = b"device_code"
        fat = FatBinaryBundler().bundle("test", host_bytes, {1: device_bytes})
        fb  = FatBinary.deserialise(fat)
        assert fb.name == "test"
        assert len(fb.sections) == 2
        tags = [s.tag for s in fb.sections]
        assert "host_code" in tags
        assert "lrbs_gen1" in tags

    def test_multi_generation(self):
        blobs = {1: b"gen1", 2: b"gen2", 3: b"gen3"}
        fat = FatBinaryBundler().bundle("multiapp", b"host", blobs)
        fb  = FatBinary.deserialise(fat)
        tags = [s.tag for s in fb.sections]
        assert "lrbs_gen1" in tags
        assert "lrbs_gen2" in tags
        assert "lrbs_gen3" in tags


class TestTernary:

    def test_quantise_basic(self):
        vals = [-1.0, 0.0, 1.0, 0.3, -0.8]
        result = quantise_to_ternary(vals, threshold=0.5)
        assert result == [-1, 0, 1, 0, -1]

    def test_round_trip(self):
        vals = [1, -1, 0, 1, 0, -1, 1, 1]
        packed = pack_ternary_word(vals)
        unpacked = unpack_ternary_word(packed, len(vals))
        assert unpacked == vals

    def test_ternary_dot(self):
        a = [1, -1, 1, 0]
        b = [1,  1, 1, 1]
        # 1*1 + (-1)*1 + 1*1 + 0*1 = 1
        assert ternary_dot(a, b) == 1

    def test_mzi_phase(self):
        import math
        phase = mzi_phase_for_weight(1.0)
        assert abs(phase) < 1e-6  # weight=1 => phase=0

        phase_half = mzi_phase_for_weight(0.5)
        # cos^2(phase/2) = 0.5 => phase = pi/2
        assert abs(phase_half - math.pi / 2) < 1e-5

    def test_ternary_encoding_pass(self):
        from lightrail.ir.ssa import Builder, Module
        from lightrail.ir.ops import Opcode
        from lightrail.ir.types import FP32

        m = Module(name="ternary_test")
        b = Builder(m)
        fn = b.new_function("f", [("a", FP32), ("b", FP32)], ret=FP32, is_device=True)
        entry = b.new_block(fn, "entry")
        b.use_block(entry)
        r = b.emit(Opcode.TDOT, operands=["a", "b"], ty=FP32, result_hint="tdot")
        b.ret(r)

        TernaryEncodingPass().run(m)
        ops = [i.op for i in fn.all_instructions()]
        assert Opcode.TERNARY_ENCODE in ops
        assert Opcode.TERNARY_DECODE in ops

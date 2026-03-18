"""Tests for Stage 4: Dataflow & WDM channel mapping."""
import pytest

from lightrail.frontend.ast_parser import ASTParser
from lightrail.passes.graph_partition import GraphPartitionPass
from lightrail.dataflow.wavelength_mapper import WavelengthMapper, NUM_CHANNELS, channel_frequency
from lightrail.dataflow.routing import DataflowRouter
from lightrail.dataflow.collective_intercept import CollectiveInterceptPass
from lightrail.ir.ops import Opcode


def _parse_device(src, fn_name):
    m = ASTParser().parse_source(src, fn_name, device=True)
    fn = m.get_function(fn_name)
    fn.is_device = True
    GraphPartitionPass().run(m)
    return m


class TestWavelengthMapper:

    def test_channel_frequency(self):
        f0 = channel_frequency(0)
        f1 = channel_frequency(1)
        assert abs(f0 - 193.1) < 1e-6
        assert abs(f1 - f0 - 0.1) < 1e-9

    def test_wdm_bind_inserted(self):
        src = """
def kernel(a, b):
    return a + b
"""
        m = _parse_device(src, "kernel")
        WavelengthMapper().run(m)
        fn = m.get_function("kernel")
        ops = [i.op for i in fn.all_instructions()]
        assert Opcode.WDM_BIND in ops

    def test_channel_annotation(self):
        src = """
def kernel(a, b, c):
    x = a + b
    y = x * c
    return y
"""
        m = _parse_device(src, "kernel")
        WavelengthMapper().run(m)
        fn = m.get_function("kernel")
        for instr in fn.all_instructions():
            if instr.result and instr.op != Opcode.WDM_BIND:
                assert "wdm_channel" in instr.attrs
                assert 0 <= instr.attrs["wdm_channel"] < NUM_CHANNELS

    def test_num_channels_used(self):
        src = """
def kernel(a, b, c):
    return a + b * c
"""
        m = _parse_device(src, "kernel")
        WavelengthMapper(num_channels=64).run(m)
        fn = m.get_function("kernel")
        assert "wdm_channels_used" in fn.attrs
        assert fn.attrs["wdm_channels_used"] >= 1


class TestDataflowRouter:

    def test_routing_table_created(self):
        src = """
def kernel(a, b):
    return a + b
"""
        m = _parse_device(src, "kernel")
        WavelengthMapper().run(m)
        DataflowRouter().run(m)
        fn = m.get_function("kernel")
        # May be empty if all ops are on same tile, but should exist
        assert "routing_table" in fn.attrs or "total_route_latency_ns" in fn.attrs

    def test_latency_non_negative(self):
        src = """
def kernel(a, b, c, d):
    x = a + b
    y = c + d
    return x + y
"""
        m = _parse_device(src, "kernel")
        WavelengthMapper().run(m)
        DataflowRouter().run(m)
        fn = m.get_function("kernel")
        lat = fn.attrs.get("total_route_latency_ns", 0.0)
        assert lat >= 0.0


class TestCollectiveIntercept:

    def test_all_reduce_annotated(self):
        src = """
def kernel(x):
    return all_reduce(x, reduction="sum")
"""
        m = ASTParser().parse_source(src, "kernel", device=True)
        CollectiveInterceptPass().run(m)
        fn = m.get_function("kernel")
        for instr in fn.all_instructions():
            if instr.op == Opcode.ALL_REDUCE:
                assert instr.attrs.get("fabric_os_collective") == "ring_allreduce"
                assert instr.attrs.get("ring_size") == 64
                assert instr.attrs.get("fabric_layer") == 19

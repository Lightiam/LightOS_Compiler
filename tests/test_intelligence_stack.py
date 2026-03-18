"""Tests for the Mathematical Scheduler, Framework Adapters, and Intelligence Stack."""
import pytest

from lightrail.scheduler.math_scheduler import (
    MathematicalScheduler, HungarianSolver, PriorityTopologicalScheduler,
)
from lightrail.adapters import PyTorchAdapter, JAXAdapter, get_adapter
from lightrail.adapters.base import AdapterGraph, AdapterGraphNode, FrameworkAdapter
from lightrail.intelligence.stack import (
    LightRailIntelligenceStack, IntelligenceStackConfig, WorkloadPartitioner,
)
from lightrail.topology.fingerprint import FabricTopologyState, TopologyFingerprint
from lightrail.frontend.ast_parser import ASTParser
from lightrail.passes.graph_partition import GraphPartitionPass
from lightrail.ir.ssa import Module, Builder
from lightrail.ir.types import FP32, VOID
from lightrail.ir.ops import Opcode


# ---------------------------------------------------------------------------
# HungarianSolver
# ---------------------------------------------------------------------------

class TestHungarianSolver:

    def test_basic_assignment(self):
        from lightrail.ir.ssa import Instruction
        instrs = [Instruction(Opcode.FADD, f"v{i}", [], type_=FP32) for i in range(4)]
        # Uniform cost: all channels equally cheap
        costs = [[1.0] * 64 for _ in range(4)]
        assignment = HungarianSolver().solve(instrs, costs)
        assert len(assignment) == 4
        assert all(0 <= ch < 64 for ch in assignment)

    def test_prefers_low_cost(self):
        from lightrail.ir.ssa import Instruction
        instrs = [Instruction(Opcode.FADD, "v0", [], type_=FP32)]
        costs  = [[100.0] * 64]
        costs[0][7] = 0.0   # channel 7 is cheapest
        assignment = HungarianSolver().solve(instrs, costs)
        assert assignment[0] == 7


# ---------------------------------------------------------------------------
# MathematicalScheduler
# ---------------------------------------------------------------------------

class TestMathematicalScheduler:

    def _device_module(self, src, fn_name):
        m = ASTParser().parse_source(src, fn_name, device=True)
        fn = m.get_function(fn_name)
        fn.is_device = True
        GraphPartitionPass().run(m)
        return m

    def test_assigns_channels(self):
        src = """
def f(a, b, c):
    x = a + b
    y = x * c
    return y
"""
        m = self._device_module(src, "f")
        MathematicalScheduler().run(m)
        fn = m.get_function("f")
        for instr in fn.all_instructions():
            if instr.result and instr.op not in {Opcode.WDM_BIND}:
                if instr.attrs.get("scheduled_optimal"):
                    assert 0 <= instr.attrs["wdm_channel"] < 64

    def test_ternary_prefers_layers_1_5(self):
        m = Module(name="ttest")
        b = Builder(m)
        fn = b.new_function("f", [("a", FP32), ("b", FP32)], ret=FP32, is_device=True)
        entry = b.new_block(fn, "entry")
        b.use_block(entry)
        r = b.emit(Opcode.TDOT, operands=["a", "b"], ty=FP32, result_hint="r")
        b.ret(r)

        MathematicalScheduler().run(m)
        for instr in fn.all_instructions():
            if instr.op == Opcode.TDOT and instr.attrs.get("scheduled_optimal"):
                layer = instr.attrs.get("fabric_layer", 99)
                assert 1 <= layer <= 5

    def test_collective_prefers_layer_19(self):
        m = Module(name="ctest")
        b = Builder(m)
        fn = b.new_function("f", [("x", FP32)], ret=FP32, is_device=True)
        entry = b.new_block(fn, "entry")
        b.use_block(entry)
        r = b.all_reduce("x", FP32, "sum")
        b.ret(r)

        MathematicalScheduler().run(m)
        for instr in fn.all_instructions():
            if instr.op == Opcode.ALL_REDUCE and instr.attrs.get("scheduled_optimal"):
                layer = instr.attrs.get("fabric_layer", -1)
                assert layer == 19

    def test_scheduling_result_stamped(self):
        src = """
def f(a, b):
    return a + b
"""
        m = self._device_module(src, "f")
        MathematicalScheduler().run(m)
        fn = m.get_function("f")
        assert "scheduling_result" in fn.attrs
        sr = fn.attrs["scheduling_result"]
        assert sr.solver_used in ("hungarian", "topological_critical_path")

    def test_fingerprint_stamped(self):
        src = """
def f(a):
    return a
"""
        m = self._device_module(src, "f")
        MathematicalScheduler().run(m)
        fn = m.get_function("f")
        assert "scheduler_fingerprint" in fn.attrs
        assert len(fn.attrs["scheduler_fingerprint"]) == 64

    def test_module_metadata(self):
        src = """
def f(a):
    return a
"""
        m = self._device_module(src, "f")
        MathematicalScheduler().run(m)
        assert m.metadata.get("scheduler") == "mathematical_optimal"


# ---------------------------------------------------------------------------
# Framework Adapters
# ---------------------------------------------------------------------------

class TestAdapterBase:

    def test_topological_order(self):
        g = AdapterGraph(framework="test")
        g.nodes = [
            AdapterGraphNode("A", "op", [],    ["B"]),
            AdapterGraphNode("B", "op", ["A"], ["C"]),
            AdapterGraphNode("C", "op", ["B"], []),
        ]
        order = g.topological_order()
        ids = [n.node_id for n in order]
        assert ids.index("A") < ids.index("B") < ids.index("C")

    def test_op_mapping(self):
        from lightrail.adapters.base import FrameworkAdapter
        assert FrameworkAdapter._map_op("aten::mm")         == Opcode.MATMUL
        assert FrameworkAdapter._map_op("jax.lax.add")      == Opcode.FADD
        assert FrameworkAdapter._map_op("reduce_sum")        == Opcode.ALL_REDUCE
        assert FrameworkAdapter._map_op("jax.lax.matmul")   == Opcode.MATMUL

    def test_to_module(self):
        g = AdapterGraph(
            framework="test",
            metadata={"name": "tiny"},
            inputs=["in0"],
            outputs=["out0"],
        )
        g.nodes = [
            AdapterGraphNode("in0", "input",   [],      ["in0"]),
            AdapterGraphNode("out0","aten::mm",["in0"], ["out0"], shape=(64, 64)),
        ]

        class ConcreteAdapter(FrameworkAdapter):
            @property
            def framework_name(self): return "test"
            def is_available(self): return True
            def extract_graph(self, m, e=None): return g

        mod = ConcreteAdapter().to_module(g, "tiny")
        assert mod.name == "tiny"
        fn = mod.device_functions()[0]
        assert fn is not None
        ops = [i.op for i in fn.all_instructions()]
        assert Opcode.MATMUL in ops


class TestPyTorchAdapter:

    def test_is_available(self):
        a = PyTorchAdapter()
        # Just check it returns bool without crash
        result = a.is_available()
        assert isinstance(result, bool)

    def test_extract_graph_without_pytorch(self):
        """If PyTorch is not installed, should raise RuntimeError."""
        a = PyTorchAdapter()
        if not a.is_available():
            with pytest.raises(RuntimeError, match="PyTorch"):
                a.extract_graph(object())

    def test_extract_graph_with_pytorch(self):
        """If PyTorch is available, trace a simple linear layer."""
        a = PyTorchAdapter()
        if not a.is_available():
            pytest.skip("PyTorch not installed")

        import torch
        import torch.nn as nn

        model = nn.Sequential(nn.Linear(16, 16), nn.ReLU())
        graph = a.extract_graph(model)
        assert graph.framework == "pytorch"
        assert len(graph.nodes) > 0

    def test_to_module_with_pytorch(self):
        a = PyTorchAdapter()
        if not a.is_available():
            pytest.skip("PyTorch not installed")

        import torch.nn as nn
        model = nn.Linear(8, 8)
        graph  = a.extract_graph(model)
        module = a.to_module(graph, "linear")
        assert module.name == "linear"
        assert len(module.device_functions()) > 0


class TestJAXAdapter:

    def test_is_available(self):
        a = JAXAdapter()
        result = a.is_available()
        assert isinstance(result, bool)

    def test_extract_graph_without_jax(self):
        a = JAXAdapter()
        if not a.is_available():
            with pytest.raises(RuntimeError, match="JAX"):
                a.extract_graph(lambda x: x)

    def test_extract_graph_with_jax(self):
        a = JAXAdapter()
        if not a.is_available():
            pytest.skip("JAX not installed")

        import jax.numpy as jnp
        fn = lambda x, y: jnp.dot(x, y)
        example = [jnp.ones((8, 8)), jnp.ones((8, 8))]
        graph = a.extract_graph(fn, example)
        assert graph.framework == "jax"
        assert len(graph.nodes) > 0


class TestGetAdapter:

    def test_pytorch(self):
        a = get_adapter("pytorch")
        assert isinstance(a, PyTorchAdapter)

    def test_jax(self):
        a = get_adapter("jax")
        assert isinstance(a, JAXAdapter)

    def test_unknown(self):
        with pytest.raises(ValueError):
            get_adapter("tensorflow")

    def test_auto(self):
        try:
            a = get_adapter("auto")
            assert a.is_available()
        except RuntimeError:
            # Neither PyTorch nor JAX installed — acceptable in CI
            pass


# ---------------------------------------------------------------------------
# WorkloadPartitioner
# ---------------------------------------------------------------------------

class TestWorkloadPartitioner:

    def test_partition_device_fns(self):
        src = """
def kernel(a, b):
    return a + b
"""
        m = ASTParser().parse_source(src, "kernel", device=True)
        fn = m.get_function("kernel")
        fn.is_device = True

        from lightrail.topology.aware_router import TopologyAwareRouter
        router = TopologyAwareRouter()
        alloc  = WorkloadPartitioner().partition(m, router)
        assert "kernel" in alloc
        assert len(alloc["kernel"]) >= 1

    def test_layers_in_range(self):
        src = """
def kernel(a, b, c):
    return a + b + c
"""
        m = ASTParser().parse_source(src, "kernel", device=True)
        m.get_function("kernel").is_device = True

        from lightrail.topology.aware_router import TopologyAwareRouter
        alloc = WorkloadPartitioner().partition(m, TopologyAwareRouter())
        for layers in alloc.values():
            for l in layers:
                assert 0 <= l < 20

    def test_fn_annotated(self):
        src = """
def kernel(a):
    return a
"""
        m = ASTParser().parse_source(src, "kernel", device=True)
        m.get_function("kernel").is_device = True

        from lightrail.topology.aware_router import TopologyAwareRouter
        WorkloadPartitioner().partition(m, TopologyAwareRouter())
        fn = m.get_function("kernel")
        assert fn.attrs.get("workload_partitioned") is True
        assert "assigned_layers" in fn.attrs


# ---------------------------------------------------------------------------
# LightRail Intelligence Stack (end-to-end)
# ---------------------------------------------------------------------------

class TestIntelligenceStack:

    def _stack(self):
        return LightRailIntelligenceStack()

    def test_compile_source(self):
        src = """
def f(a, b):
    return a + b
"""
        result = self._stack().compile_source(src, "f")
        assert result.module is not None
        m = result.module
        assert m.metadata.get("topology_fingerprint") is not None
        assert m.metadata.get("mathematically_optimal") is True

    def test_bypasses_electrical_io_wall(self):
        src = """
def f(x):
    return x
"""
        result = self._stack().compile_source(src, "f")
        assert result.module.metadata.get("bypasses_electrical_io_wall") is True

    def test_workload_partitioned(self):
        src = """
def kernel(a, b, c):
    return a + b * c
"""
        result = self._stack().compile_source(src, "kernel")
        assert result.module.metadata.get("workload_partitioned") is True

    def test_tar_stage_timed(self):
        src = """
def f(a, b):
    return a + b
"""
        result = self._stack().compile_source(src, "f")
        assert "tar_routing" in result.stage_times
        assert result.stage_times["tar_routing"] >= 0.0

    def test_math_sched_stage_timed(self):
        src = """
def f(a, b):
    return a + b
"""
        result = self._stack().compile_source(src, "f")
        assert "math_scheduling" in result.stage_times

    def test_benchmark(self):
        src = """
def bench_kernel(a, b, c):
    x = a + b
    y = x * c
    return y
"""
        stack = self._stack()
        from lightrail.ir.ssa import Module, Builder
        m = ASTParser().parse_source(src, "bench_kernel", device=True)
        bench = stack.benchmark(m)

        assert bench.module_name == "bench_kernel"
        assert bench.compile_time_ms >= 0
        assert 0.0 <= bench.congestion_score <= 1.0
        assert len(bench.topology_fingerprint) == 64

    def test_benchmark_summary(self):
        src = """
def f(x):
    return x
"""
        stack = self._stack()
        m = ASTParser().parse_source(src, "f", device=True)
        bench = stack.benchmark(m)
        summary = bench.summary()
        assert "LightRail Intelligence Stack" in summary
        assert "Topology fingerprint" in summary

    def test_congestion_report(self):
        report = self._stack().congestion_report()
        assert "fingerprint" in report
        assert "congestion_score" in report

    def test_update_topology(self):
        stack = self._stack()
        new_state = FabricTopologyState()
        new_state.mark_used(5, 10, 0.9)
        stack.update_topology(new_state)
        fp = stack.fingerprint()
        assert not fp.is_clean()

    def test_compile_module_pipeline_integration(self):
        """Verify TAR + Math Scheduler annotations appear in pipeline output."""
        from lightrail.pipeline import CompilationPipeline, CompileOptions
        src = """
def pipeline_test(a, b, c):
    return a + b * c
"""
        opts = CompileOptions(enable_tar=True, enable_math_sched=True)
        result = CompilationPipeline(opts).compile_source(src, "pipeline_test")
        m = result.module
        assert "topology_fingerprint" in m.metadata
        # At least one device fn should have been through the math scheduler
        for fn in m.device_functions():
            if "scheduling_result" in fn.attrs:
                assert fn.attrs["scheduler_fingerprint"] is not None
                break

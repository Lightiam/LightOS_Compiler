"""
LightRail Photonic Compiler  —  LightOS AI Compiler
=====================================================
A 6-stage compiler for the LightRail Neural Compute Engine (NCE) and its
20-layer photonic fabric interconnects, incorporating the full LightRail
Intelligence Stack (LRIS):

  - Topology-Aware Router  : Mathematically provable Dijkstra routing with
                             unique Topology Fingerprints per fabric state.
  - Mathematical Scheduler : Hungarian / critical-path optimal WDM assignment.
  - Workload Partitioner   : Splits AI models across 20 NCE fabric tiles.
  - Framework Adapters     : PyTorch and JAX graph ingestion.
  - 6-Stage Pipeline       : Parse → Lower → Optimise → Map → Bytecode → Run.

Quick start:
    import lightrail

    @lightrail.jit
    def dot_product(A: "float32", B: "float32", N: "int32") -> "float32":
        acc: float32 = 0.0
        for i in range(N):
            acc += A[i] * B[i]
        return acc

    result = dot_product(a_buf, b_buf, 1024)

Full Intelligence Stack:
    stack = lightrail.IntelligenceStack()
    result = stack.compile_function(my_fn)
    bench  = stack.benchmark(my_fn)
    print(bench.summary())
"""

from lightrail.decorators import jit, LightRailKernel
from lightrail.pipeline import CompilationPipeline, CompileOptions, CompilationResult
from lightrail.ir import (
    Module, Function, BasicBlock, Builder,
    INT8, INT16, INT32, INT64, FP8, FP16, BF16, ABFP16, FP32, FP64,
    TERNARY, ANALOG, VOID, BOOL,
)
from lightrail.runtime import AOTCompiler, JITRunner, get_default_scheduler

# Intelligence Stack
from lightrail.intelligence.stack import (
    LightRailIntelligenceStack as IntelligenceStack,
    IntelligenceStackConfig,
    BenchmarkResult,
)
from lightrail.topology import (
    TopologyAwareRouter,
    TopologyFingerprint,
    FabricTopologyState,
)
from lightrail.scheduler import MathematicalScheduler
from lightrail.adapters import get_adapter, PyTorchAdapter, JAXAdapter

__version__ = "0.2.0"
__author__  = "LightRail Compiler Team"

__all__ = [
    # Decorator API
    "jit",
    "LightRailKernel",
    # Pipeline
    "CompilationPipeline",
    "CompileOptions",
    "CompilationResult",
    # Intelligence Stack
    "IntelligenceStack",
    "IntelligenceStackConfig",
    "BenchmarkResult",
    # Topology
    "TopologyAwareRouter",
    "TopologyFingerprint",
    "FabricTopologyState",
    # Scheduler
    "MathematicalScheduler",
    # Framework Adapters
    "get_adapter",
    "PyTorchAdapter",
    "JAXAdapter",
    # IR types
    "Module", "Function", "BasicBlock", "Builder",
    "INT8", "INT16", "INT32", "INT64",
    "FP8", "FP16", "BF16", "ABFP16", "FP32", "FP64",
    "TERNARY", "ANALOG", "VOID", "BOOL",
    # Runtime
    "AOTCompiler",
    "JITRunner",
    "get_default_scheduler",
]

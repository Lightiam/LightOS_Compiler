"""
LightRail Photonic Compiler
============================
A 6-stage compiler for the LightRail Neural Compute Engine (NCE) and its
20-layer photonic fabric interconnects.

Quick start:
    import lightrail

    @lightrail.jit
    def dot_product(A: "float32", B: "float32", N: "int32") -> "float32":
        acc: float32 = 0.0
        for i in range(N):
            acc += A[i] * B[i]
        return acc

    result = dot_product(a_buf, b_buf, 1024)

Pipeline stages:
  1. AST Parsing & High-Level IR
  2. Type Inference & Lowering
  3. Photonic-Aware Optimisation (FMA, Loop Splitting, Graph Partitioning)
  4. Dataflow & WDM Channel Mapping (replaces CUDA thread scheduling)
  5. Tile Bytecode & Fat Binary Generation (.lrbs / .lrfat)
  6. Execution & Fabric OS Handoff (AOT or JIT)
"""

from lightrail.decorators import jit, LightRailKernel
from lightrail.pipeline import CompilationPipeline, CompileOptions, CompilationResult
from lightrail.ir import (
    Module, Function, BasicBlock, Builder,
    INT8, INT16, INT32, INT64, FP8, FP16, BF16, ABFP16, FP32, FP64,
    TERNARY, ANALOG, VOID, BOOL,
)
from lightrail.runtime import AOTCompiler, JITRunner, get_default_scheduler

__version__ = "0.1.0"
__author__  = "LightRail Compiler Team"

__all__ = [
    # Decorator API
    "jit",
    "LightRailKernel",
    # Pipeline
    "CompilationPipeline",
    "CompileOptions",
    "CompilationResult",
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

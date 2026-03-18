"""
LightRail 6-Stage Compilation Pipeline Orchestrator
=====================================================
Ties all compiler stages together into a single, unified pipeline that
takes a Python function (or C++ source file) and produces either:

  - An AOTBinary (.lrnpu) for direct Fabric OS loading, or
  - A JITRunner that compiles-on-demand and caches results.

Pipeline stages (in order):
  1. AST Parsing & High-Level IR           (frontend.ASTParser)
  2. Host/Device Split                     (frontend.HostDeviceSplitter)
  3. Type Inference & Lowering             (passes.TypeInferencePass)
     Dead Code Elimination                 (passes.DeadCodeEliminationPass)
  4. Photonic-Aware Optimisation Passes:
       Alias Analysis                      (passes.AliasAnalysisPass)
       Loop Splitting / Tile Pipelining    (passes.LoopSplittingPass)
       FMA Fusion                          (passes.FMAFusionPass)
       Graph Partitioning                  (passes.GraphPartitionPass)
  5. Ternary / Analog Encoding             (codegen.TernaryEncodingPass)
  6. Dataflow & Wavelength Mapping         (dataflow.WavelengthMapper)
       Collective Intercept                (dataflow.CollectiveInterceptPass)
       Dataflow Routing                    (dataflow.DataflowRouter)
  7. Bytecode Generation                   (codegen.BytecodeEmitter)
  8. Fat Binary Bundling                   (codegen.FatBinaryBundler)

Execution:
  9. AOT: AOTCompiler                      (runtime.AOTCompiler)
     JIT: JITRunner + FabricOSClient       (runtime.JITRunner)
"""

from __future__ import annotations
import pickle
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from lightrail.frontend.ast_parser       import ASTParser
from lightrail.frontend.host_device_split import HostDeviceSplitter
from lightrail.passes.type_inference     import TypeInferencePass
from lightrail.passes.dead_code          import DeadCodeEliminationPass
from lightrail.passes.alias_analysis     import AliasAnalysisPass
from lightrail.passes.loop_splitting     import LoopSplittingPass
from lightrail.passes.fma_fusion         import FMAFusionPass
from lightrail.passes.graph_partition    import GraphPartitionPass
from lightrail.codegen.ternary           import TernaryEncodingPass
from lightrail.dataflow.wavelength_mapper  import WavelengthMapper
from lightrail.dataflow.collective_intercept import CollectiveInterceptPass
from lightrail.dataflow.routing            import DataflowRouter
from lightrail.codegen.bytecode          import BytecodeEmitter, LRBS_FLAGS_JIT, LRBS_FLAGS_AOT
from lightrail.codegen.fat_binary        import FatBinaryBundler
from lightrail.runtime.aot              import AOTCompiler, AOTBinary
from lightrail.runtime.jit              import JITRunner
from lightrail.runtime.fabric_os        import get_default_scheduler
from lightrail.ir.ssa                   import Module


# ---------------------------------------------------------------------------
# Compilation options
# ---------------------------------------------------------------------------

@dataclass
class CompileOptions:
    """Knobs for the compilation pipeline."""
    # Stage 3 opts
    enable_fma:         bool = True
    enable_loop_split:  bool = True
    enable_alias:       bool = True
    enable_graph_part:  bool = True
    # Stage 4 opts
    num_wdm_channels:   int  = 64
    enable_ternary:     bool = True
    # Stage 5 opts
    nce_generation:     int  = 1
    fat_binary:         bool = True
    # Stage 6 opts
    mode:               str  = "jit"   # "jit" | "aot"
    debug:              bool = False
    # Intelligence Stack opts
    enable_tar:         bool = True    # Topology-Aware Router
    enable_math_sched:  bool = True    # Mathematical Scheduler


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@dataclass
class CompilationResult:
    module:        Module
    lrbs_bytes:    bytes
    fat_binary_bytes: Optional[bytes]
    aot_binary:    Optional[AOTBinary]
    compile_time_s: float
    stage_times:   Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"Module: {self.module.name}",
            f"Device functions: {len(self.module.device_functions())}",
            f"Total compile time: {self.compile_time_s*1000:.1f} ms",
            f"LRBS size: {len(self.lrbs_bytes)} bytes",
        ]
        if self.fat_binary_bytes:
            lines.append(f"Fat binary size: {len(self.fat_binary_bytes)} bytes")
        if self.aot_binary:
            lines.append(f"AOT binary: {len(self.aot_binary.npu_code)} bytes NPU code")
        # Intelligence Stack metadata
        fp = self.module.metadata.get("topology_fingerprint")
        if fp:
            lines.append(f"Topology fingerprint: {fp[:24]}...")
        if self.module.metadata.get("mathematically_optimal"):
            lines.append("Routing: mathematically optimal (Dijkstra TAR)")
        solver = None
        for fn in self.module.device_functions():
            sr = fn.attrs.get("scheduling_result")
            if sr:
                solver = sr.solver_used
                break
        if solver:
            lines.append(f"Scheduler: {solver}")
        if self.module.metadata.get("workload_partitioned"):
            lines.append("Workload: partitioned across NCE tiles")
        if self.stage_times:
            lines.append("Stage timings (ms):")
            for stage, t in self.stage_times.items():
                lines.append(f"  {stage}: {t*1000:.2f}")
        return "\n".join(lines)


class CompilationPipeline:
    """
    The LightRail 6-stage compilation pipeline.

    Usage:
        pipeline = CompilationPipeline()
        result   = pipeline.compile_function(my_fn, opts=CompileOptions(mode="aot"))
    """

    def __init__(self, opts: Optional[CompileOptions] = None) -> None:
        self.opts = opts or CompileOptions()

    def compile_function(
        self,
        fn: Callable,
        device: bool = True,
    ) -> CompilationResult:
        """Compile a Python callable through the full pipeline."""
        t_start = time.perf_counter()
        stages: Dict[str, float] = {}

        def timed(name: str, fn_):
            t = time.perf_counter()
            result = fn_()
            stages[name] = time.perf_counter() - t
            return result

        # Stage 1: Parse
        parser = ASTParser()
        module = timed("1_parse", lambda: parser.parse_function(fn, device=device))

        return self._run_backend(module, stages, t_start, fn)

    def compile_source(
        self,
        source: str,
        fn_name: str,
        device: bool = True,
    ) -> CompilationResult:
        """Compile Python source text through the full pipeline."""
        t_start = time.perf_counter()
        stages: Dict[str, float] = {}

        def timed(name: str, fn_):
            t = time.perf_counter()
            result = fn_()
            stages[name] = time.perf_counter() - t
            return result

        parser = ASTParser()
        module = timed("1_parse", lambda: parser.parse_source(source, fn_name, device=device))

        return self._run_backend(module, stages, t_start, None)

    def compile_module(self, module: Module) -> CompilationResult:
        """Compile an already-constructed IR Module."""
        t_start = time.perf_counter()
        stages: Dict[str, float] = {}
        return self._run_backend(module, stages, t_start, None)

    # -- Backend (stages 2-9) ------------------------------------------------

    def _run_backend(
        self,
        module:   Module,
        stages:   Dict[str, float],
        t_start:  float,
        original_fn: Optional[Callable],
    ) -> CompilationResult:
        opts = self.opts

        def timed(name: str, fn_):
            t = time.perf_counter()
            result = fn_()
            stages[name] = time.perf_counter() - t
            return result

        # Stage 1b: Host/Device Split
        timed("1b_split", lambda: HostDeviceSplitter().run(module))

        # Stage 2: Type Inference + DCE
        timed("2_type_infer",  lambda: TypeInferencePass().run(module))
        timed("2_dce",         lambda: DeadCodeEliminationPass().run(module))

        # Stage 3: Photonic-Aware Optimisation
        if opts.enable_alias:
            timed("3_alias",     lambda: AliasAnalysisPass().run(module))
        if opts.enable_loop_split:
            timed("3_loop_split",lambda: LoopSplittingPass().run(module))
        if opts.enable_fma:
            timed("3_fma",       lambda: FMAFusionPass().run(module))
        if opts.enable_graph_part:
            timed("3_graph_part",lambda: GraphPartitionPass().run(module))

        # Ternary/Analog encoding
        if opts.enable_ternary:
            timed("3_ternary",   lambda: TernaryEncodingPass().run(module))

        # Stage 4: Dataflow & WDM Mapping
        timed("4_collective",    lambda: CollectiveInterceptPass().run(module))
        mapper = WavelengthMapper(num_channels=opts.num_wdm_channels)
        timed("4_wdm_map",       lambda: mapper.run(module))
        timed("4_routing",       lambda: DataflowRouter().run(module))

        # Intelligence Stack — Topology-Aware Router (replaces heuristic routing)
        if opts.enable_tar:
            from lightrail.topology.aware_router import TopologyAwareRouter
            timed("4_tar",       lambda: TopologyAwareRouter().run(module))

        # Intelligence Stack — Mathematical Scheduler (replaces greedy WDM assignment)
        if opts.enable_math_sched:
            from lightrail.scheduler.math_scheduler import MathematicalScheduler
            timed("4_math_sched", lambda: MathematicalScheduler().run(module))

        # Stage 5: Bytecode + Fat Binary
        emitter = BytecodeEmitter()
        flags = LRBS_FLAGS_AOT if opts.mode == "aot" else LRBS_FLAGS_JIT
        lrbs_bytes = timed("5_bytecode", lambda: emitter.emit(module, flags=flags))

        fat_bytes: Optional[bytes] = None
        if opts.fat_binary:
            try:
                host_bytes = pickle.dumps(original_fn) if original_fn else b""
            except (pickle.PicklingError, AttributeError):
                host_bytes = b""
            bundler = FatBinaryBundler()
            fat_bytes = timed(
                "5_fat_binary",
                lambda: bundler.bundle(
                    name=module.name,
                    host_bytes=host_bytes,
                    device_blobs={opts.nce_generation: lrbs_bytes},
                    manifest_extra={
                        "wdm_channels": opts.num_wdm_channels,
                        "nce_generation": opts.nce_generation,
                    },
                ),
            )

        # Stage 6: AOT or JIT preparation
        aot_binary: Optional[AOTBinary] = None
        if opts.mode == "aot":
            aot_compiler = AOTCompiler(nce_generation=opts.nce_generation)
            aot_binary = timed("6_aot", lambda: aot_compiler.compile(module))

        total_time = time.perf_counter() - t_start

        return CompilationResult(
            module=module,
            lrbs_bytes=lrbs_bytes,
            fat_binary_bytes=fat_bytes,
            aot_binary=aot_binary,
            compile_time_s=total_time,
            stage_times=stages,
        )

    def make_jit_runner(self, fn: Callable) -> JITRunner:
        """
        Create a JITRunner for a Python function.  On first call, the runner
        compiles and caches; subsequent calls dispatch from cache.
        """
        opts = self.opts

        def compile_fn(args: tuple) -> Module:
            result = self.compile_function(fn, device=True)
            return result.module

        return JITRunner(
            fn_name=fn.__qualname__,
            compile_fn=compile_fn,
            scheduler=get_default_scheduler(),
        )

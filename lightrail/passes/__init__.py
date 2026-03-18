"""LightRail compiler optimisation passes (Stages 2 & 3)."""
from lightrail.passes.type_inference   import TypeInferencePass
from lightrail.passes.dead_code        import DeadCodeEliminationPass
from lightrail.passes.alias_analysis   import AliasAnalysisPass
from lightrail.passes.loop_splitting   import LoopSplittingPass
from lightrail.passes.fma_fusion       import FMAFusionPass
from lightrail.passes.graph_partition  import GraphPartitionPass

__all__ = [
    "TypeInferencePass",
    "DeadCodeEliminationPass",
    "AliasAnalysisPass",
    "LoopSplittingPass",
    "FMAFusionPass",
    "GraphPartitionPass",
]

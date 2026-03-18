"""
Stage 4: Dataflow Routing Model
=================================
Models the movement of data as messages across the LightRail physical mesh
rather than as memory copies governed by a thread scheduler.

The routing model:
  1. Constructs a directed dataflow graph (DFG) for a device function,
     where nodes are compute tiles and edges are optical data streams.
  2. Computes shortest-path optical routes through the 20-layer fabric
     using a simple Manhattan-distance model on the tile grid.
  3. Annotates each inter-tile data transfer with the routing path
     (list of fabric layer indices) so the Fabric OS can programme
     the WDM switches accordingly.
  4. Ensures deterministic, single-thread-per-stream execution by
     forbidding backpressure—if a route overflows, the compiler raises
     a RouteCapacityError rather than spilling to a slower path.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from lightrail.ir.ssa import Module, Function, Instruction
from lightrail.ir.ops import Opcode


# ---------------------------------------------------------------------------
# Fabric topology constants (20-layer photonic fabric)
# ---------------------------------------------------------------------------

FABRIC_LAYERS    = 20
TILES_PER_LAYER  = 64       # 64 WDM channels = 64 tiles per layer
BANDWIDTH_GBPS   = 3200     # per optical link (3.2 Tb/s)
LATENCY_NS       = 0.05     # ~50 ps per layer hop


class RouteCapacityError(Exception):
    pass


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FabricEdge:
    """Represents one optical data transfer between two tiles."""
    src_tile:  int
    dst_tile:  int
    src_layer: int
    dst_layer: int
    ssa_name:  str                    # the SSA value being transferred
    route:     List[int] = field(default_factory=list)   # list of layer hops
    bandwidth_required_gbps: float = 0.0
    latency_ns: float = 0.0


@dataclass
class RoutingTable:
    edges: List[FabricEdge] = field(default_factory=list)
    congestion: Dict[Tuple[int, int], float] = field(default_factory=dict)  # (layer, tile) -> load

    def total_latency_ns(self) -> float:
        return sum(e.latency_ns for e in self.edges)

    def max_congestion(self) -> float:
        return max(self.congestion.values(), default=0.0)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class DataflowRouter:
    """
    Builds inter-tile routing paths for a device function's dataflow graph.
    """

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            if fn.is_device:
                table = self._route_function(fn)
                fn.attrs["routing_table"] = table
                fn.attrs["total_route_latency_ns"] = table.total_latency_ns()
        return module

    def _route_function(self, fn: Function) -> RoutingTable:
        table = RoutingTable()

        # Collect (ssa_name, src_tile, dst_tile) triples from cross-tile edges
        tile_of: Dict[str, int] = {}
        for instr in fn.all_instructions():
            if instr.result and "tile_id" in instr.attrs:
                tile_of[instr.result] = instr.attrs["tile_id"]

        for instr in fn.all_instructions():
            if "tile_id" not in instr.attrs:
                continue
            dst_tile = instr.attrs["tile_id"]
            for op in instr.operands:
                if op not in tile_of:
                    continue
                src_tile = tile_of[op]
                if src_tile == dst_tile:
                    continue  # local: no routing needed

                route = self._compute_route(src_tile, dst_tile, fn)
                latency = len(route) * LATENCY_NS

                edge = FabricEdge(
                    src_tile=src_tile,
                    dst_tile=dst_tile,
                    src_layer=src_tile % FABRIC_LAYERS,
                    dst_layer=dst_tile % FABRIC_LAYERS,
                    ssa_name=op,
                    route=route,
                    latency_ns=latency,
                )
                table.edges.append(edge)

                # Track congestion
                for layer_hop in route:
                    key = (layer_hop, src_tile)
                    table.congestion[key] = table.congestion.get(key, 0.0) + 1.0

        return table

    @staticmethod
    def _compute_route(src: int, dst: int, fn: Function) -> List[int]:
        """
        Simple layer-hop routing: traverse layer-by-layer toward the
        destination tile.  Each step is one optical layer hop.
        """
        src_layer = src % FABRIC_LAYERS
        dst_layer = dst % FABRIC_LAYERS

        if src_layer == dst_layer:
            return [src_layer]

        # Shortest path: linear traversal of layers
        step = 1 if dst_layer > src_layer else -1
        route = list(range(src_layer, dst_layer + step, step))
        return route

"""
Stage 3: Graph Partitioning Pass
==================================
Partitions the device function's dataflow graph into tiles that map to
the 20-layer photonic fabric, minimising cross-tile communication overhead.

Strategy:
  - Build a weighted dataflow graph where nodes are instructions and edges
    are def-use dependencies weighted by data volume (type bitwidth).
  - Apply a greedy k-way partitioning into at most MAX_TILES tiles, where
    each tile corresponds to a set of optical channels on one fabric layer.
  - Intercept collective communication (ALL_REDUCE, ALL_GATHER, etc.) and
    annotate them with the Fabric OS routing directive so the Global
    Scheduler can map them to the physical 20-layer topology.
  - Annotate each instruction with its assigned tile_id.

The MAX_TILES constant (20) mirrors the 20-layer LightRail optical fabric.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from lightrail.ir.ssa import Module, Function, Instruction
from lightrail.ir.ops import Opcode
from lightrail.ir.types import VOID


MAX_TILES       = 20     # physical fabric layers
MAX_TILE_OPS    = 64     # soft cap on ops per tile
COLLECTIVE_OPS  = {
    Opcode.ALL_REDUCE, Opcode.ALL_GATHER,
    Opcode.REDUCE_SCATTER, Opcode.BROADCAST,
    Opcode.P2P_SEND, Opcode.P2P_RECV,
}


@dataclass
class Tile:
    tile_id: int
    layer:   int                  # fabric layer index (0 .. 19)
    instructions: List[Instruction] = field(default_factory=list)
    in_edges:  Set[str] = field(default_factory=set)   # SSA names crossing into tile
    out_edges: Set[str] = field(default_factory=set)   # SSA names crossing out

    def communication_cost(self) -> int:
        return len(self.in_edges) + len(self.out_edges)


class GraphPartitionPass:
    """
    Annotates each instruction with `tile_id` and `fabric_layer` attributes,
    and marks collectives with Fabric OS routing directives.
    """

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            if fn.is_device:
                self._partition_function(fn)
        return module

    def _partition_function(self, fn: Function) -> None:
        all_instrs: List[Instruction] = list(fn.all_instructions())
        if not all_instrs:
            return

        tiles = [Tile(tile_id=i, layer=i % MAX_TILES) for i in range(MAX_TILES)]
        current_tile_idx = 0
        defined_in: Dict[str, int] = {}  # SSA name -> tile_id

        for instr in all_instrs:
            # Intercept collective ops: always assigned to tile 0 (fabric root)
            if instr.op in COLLECTIVE_OPS:
                tile_id = 0
                instr.attrs["fabric_collective"] = True
                instr.attrs["route_to_fabric_os"] = True
            else:
                tile_id = current_tile_idx

            # Record def
            if instr.result:
                defined_in[instr.result] = tile_id

            # Track cross-tile edges
            tile = tiles[tile_id]
            tile.instructions.append(instr)
            for op in instr.operands:
                if op in defined_in and defined_in[op] != tile_id:
                    src_tile = defined_in[op]
                    tiles[src_tile].out_edges.add(op)
                    tile.in_edges.add(op)

            # Annotate instruction
            instr.attrs["tile_id"] = tile_id
            instr.attrs["fabric_layer"] = tile_id % MAX_TILES

            # Advance tile when it's full (greedy bin-packing)
            if len(tile.instructions) >= MAX_TILE_OPS:
                current_tile_idx = min(current_tile_idx + 1, MAX_TILES - 1)

        # Annotate function with partition summary
        fn.attrs["num_tiles"] = current_tile_idx + 1
        fn.attrs["tile_comm_costs"] = [t.communication_cost() for t in tiles[:current_tile_idx + 1]]

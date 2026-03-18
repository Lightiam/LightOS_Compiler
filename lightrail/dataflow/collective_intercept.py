"""
Stage 4: Collective Communication Intercept
============================================
Intercepts high-level collective primitives (ALL_REDUCE, ALL_GATHER, etc.)
at the lowest compiler level and replaces them with Fabric OS routing
directives that map directly to the 20-layer photonic topology.

This is conceptually equivalent to what NCCL does for NVIDIA GPUs, but
instead of generating CUDA kernel calls, we emit optical routing metadata
that the LightRail Fabric OS interprets to programme the WDM switch fabric.

Supported collectives and their photonic mappings:
  ALL_REDUCE    -> Ring-allreduce over WDM channels; uses optical broadcast
                   on layer 19 (the "global fabric layer")
  ALL_GATHER    -> Fan-out over photonic tree topology (layers 15-19)
  REDUCE_SCATTER-> Inverse of ALL_GATHER; fan-in reduction
  BROADCAST     -> Single-source optical broadcast (wavelength copy)
  P2P_SEND/RECV -> Direct point-to-point wavelength routing
"""

from __future__ import annotations
from typing import Dict, List

from lightrail.ir.ssa import Module, Function, Instruction
from lightrail.ir.ops import Opcode
from lightrail.ir.types import VOID


GLOBAL_FABRIC_LAYER = 19   # Layer 19: global interconnect backbone
TREE_LAYERS         = list(range(15, 20))  # Layers 15-19: tree topology


_COLLECTIVE_TO_PATTERN: Dict[Opcode, str] = {
    Opcode.ALL_REDUCE:     "ring_allreduce",
    Opcode.ALL_GATHER:     "photonic_fan_out",
    Opcode.REDUCE_SCATTER: "photonic_fan_in",
    Opcode.BROADCAST:      "wavelength_copy",
    Opcode.P2P_SEND:       "direct_wdm_route",
    Opcode.P2P_RECV:       "direct_wdm_route",
}


class CollectiveInterceptPass:
    """
    Lowers collective IR operations to Fabric OS routing directives.
    """

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            for bb in fn.blocks:
                self._intercept_block(bb)
        return module

    def _intercept_block(self, bb) -> None:
        for instr in bb.instructions:
            if instr.op not in _COLLECTIVE_TO_PATTERN:
                continue

            pattern = _COLLECTIVE_TO_PATTERN[instr.op]
            instr.attrs["fabric_os_collective"] = pattern
            instr.attrs["routed_by_fabric_os"]  = True

            # ALL_REDUCE: annotate with ring topology across all WDM channels
            if instr.op == Opcode.ALL_REDUCE:
                reduction = instr.attrs.get("reduction", "sum")
                instr.attrs["ring_size"]     = 64   # all WDM channels participate
                instr.attrs["fabric_layer"]  = GLOBAL_FABRIC_LAYER
                instr.attrs["reduction_op"]  = reduction
                instr.attrs["latency_model"] = "log2(64) * hop_latency"

            # ALL_GATHER / REDUCE_SCATTER: use tree topology layers
            elif instr.op in (Opcode.ALL_GATHER, Opcode.REDUCE_SCATTER):
                instr.attrs["tree_layers"]   = TREE_LAYERS
                instr.attrs["fanout"]        = 2    # binary tree
                instr.attrs["latency_model"] = "log2(64) * hop_latency"

            # BROADCAST: single-source wavelength copy
            elif instr.op == Opcode.BROADCAST:
                instr.attrs["broadcast_layer"] = GLOBAL_FABRIC_LAYER
                instr.attrs["latency_model"]   = "O(1) optical broadcast"

            # P2P: direct wavelength-to-wavelength routing
            elif instr.op in (Opcode.P2P_SEND, Opcode.P2P_RECV):
                peer = instr.attrs.get("peer", -1)
                instr.attrs["route_layers"] = [peer % 20]
                instr.attrs["latency_model"] = "O(hops) direct route"

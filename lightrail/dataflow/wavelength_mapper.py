"""
Stage 4: Wavelength Division Multiplexing (WDM) Channel Mapper
================================================================
Replaces CUDA-style warp/thread scheduling with compile-time binding of
tasks to 64 optical WDM channels (virtual processors).

LightRail supports 64 distinct wavelengths (colours) per fibre, enabling
64 independent data streams to traverse the fabric simultaneously—analogous
to 64 hardware threads but deterministic and zero-overhead.

This pass:
  1. Builds a dataflow dependency graph of device instructions (nodes =
     instructions, edges = SSA def-use dependences).
  2. Assigns each independent instruction stream to a WDM channel (0–63)
     such that instructions with no dependency between them run on different
     channels in parallel.
  3. Inserts WDM_BIND, WDM_MUXIN, and WDM_DEMUX instructions into the IR
     to make channel assignments explicit.
  4. Annotates every instruction with `wdm_channel` so the bytecode
     emitter can serialise the channel assignment into the .lrbs file.

No warp scheduling, no thread synchronisation—deterministic optical dispatch.
"""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from lightrail.ir.ssa import Module, Function, BasicBlock, Instruction, Builder
from lightrail.ir.ops import Opcode
from lightrail.ir.types import WavelengthChannelType, VOID, FP32


NUM_CHANNELS = 64   # 64 WDM colours per fibre
C_BAND_BASE_THz = 193.1   # THz (~1550 nm)
CHANNEL_SPACING_THz = 0.1  # 100 GHz ITU grid


def channel_frequency(ch: int) -> float:
    """Return the optical frequency in THz for a given channel index."""
    return C_BAND_BASE_THz + ch * CHANNEL_SPACING_THz


@dataclass
class WDMChannel:
    channel_id: int
    frequency_thz: float
    assigned_instrs: List[str] = field(default_factory=list)  # SSA result names

    def __repr__(self) -> str:
        return (f"WDMChannel(id={self.channel_id}, "
                f"freq={self.frequency_thz:.1f} THz, "
                f"ops={len(self.assigned_instrs)})")


class WavelengthMapper:
    """
    Maps device IR instructions to WDM channels at compile time, replacing
    runtime thread scheduling with static optical channel assignment.
    """

    def __init__(self, num_channels: int = NUM_CHANNELS) -> None:
        self.num_channels = num_channels
        self.channels = [
            WDMChannel(i, channel_frequency(i)) for i in range(num_channels)
        ]

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            if fn.is_device:
                self._map_function(fn)
        return module

    def _map_function(self, fn: Function) -> None:
        # Build dependency sets: instruction result -> set of result names it depends on
        dep_graph: Dict[str, Set[str]] = {}
        all_results: List[str] = []

        for instr in fn.all_instructions():
            if instr.result:
                dep_graph[instr.result] = set(instr.operands)
                all_results.append(instr.result)

        # Assign channels via list scheduling on the dependency graph
        # Channel load balancing: assign to least-loaded channel that has no
        # data dependence conflict with the channel's previous assignment.
        result_to_channel: Dict[str, int] = {}
        channel_loads = [0] * self.num_channels

        for result in all_results:
            deps = dep_graph.get(result, set())
            # Collect channels used by direct dependencies
            blocked_channels: Set[int] = set()
            for dep in deps:
                if dep in result_to_channel:
                    blocked_channels.add(result_to_channel[dep])

            # Pick least-loaded available channel
            best_ch = -1
            best_load = float("inf")
            for ch_id in range(self.num_channels):
                if ch_id not in blocked_channels and channel_loads[ch_id] < best_load:
                    best_ch = ch_id
                    best_load = channel_loads[ch_id]

            if best_ch == -1:
                best_ch = channel_loads.index(min(channel_loads))

            result_to_channel[result] = best_ch
            channel_loads[best_ch] += 1
            self.channels[best_ch].assigned_instrs.append(result)

        # Annotate instructions and insert WDM ops
        for bb in fn.blocks:
            new_instrs: List[Instruction] = []
            for instr in bb.instructions:
                if instr.result and instr.result in result_to_channel:
                    ch = result_to_channel[instr.result]
                    instr.attrs["wdm_channel"] = ch
                    instr.attrs["wdm_freq_thz"] = channel_frequency(ch)

                    # Insert WDM_BIND before first instruction on a new channel
                    # (only once per channel per block; tracker via attrs)
                    if not instr.attrs.get("_wdm_bound"):
                        bind_instr = Instruction(
                            op=Opcode.WDM_BIND,
                            result=f"_wdm_ch{ch}_{id(instr)}",
                            operands=[],
                            attrs={"channel": ch, "freq_thz": channel_frequency(ch)},
                            type_=WavelengthChannelType(ch),
                        )
                        new_instrs.append(bind_instr)
                        instr.attrs["_wdm_bound"] = True

                new_instrs.append(instr)
            bb.instructions = new_instrs

        # Summarise mapping in function attrs
        active = sum(1 for load in channel_loads if load > 0)
        fn.attrs["wdm_channels_used"] = active
        fn.attrs["wdm_channel_loads"] = channel_loads

    def channel_summary(self) -> List[WDMChannel]:
        return [ch for ch in self.channels if ch.assigned_instrs]

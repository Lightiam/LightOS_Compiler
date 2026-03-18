"""
Stage 6: Ahead-of-Time (AOT) Compilation
==========================================
Provides the AOT compilation path: takes a compiled Module + .lrbs bytes and
generates a self-contained NPU machine-code binary that the Fabric OS can
load and execute without any JIT overhead.

AOT output format (.lrnpu):
  - .lrbs bytecode translated to NCE native instruction set (simulated here).
  - Static WDM channel assignments embedded as switch-programming tables.
  - Routing tables pre-computed and stored as binary lookup tables.
  - No driver-side compilation required at load time.

This is the preferred deployment mode for production inference workloads
where sub-microsecond cold-start latency is required.
"""

from __future__ import annotations
import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from lightrail.codegen.bytecode import BytecodeEmitter, LRBS_FLAGS_AOT
from lightrail.ir.ssa import Module
from lightrail.runtime.fabric_os import KernelDescriptor, GlobalScheduler, get_default_scheduler


LRNPU_MAGIC   = b"LNPU"
LRNPU_VERSION = (0, 1)


@dataclass
class AOTBinary:
    """Compiled AOT binary targeting a specific NCE generation."""
    name:              str
    nce_generation:    int
    npu_code:          bytes    # NCE native instruction stream
    switch_tables:     bytes    # WDM switch programming tables
    routing_tables:    bytes    # Pre-computed routing lookup tables
    metadata:          Dict[str, str] = field(default_factory=dict)

    def serialise(self) -> bytes:
        """Serialise to .lrnpu bytes."""
        parts = [LRNPU_MAGIC]
        parts.append(struct.pack(">BBH", LRNPU_VERSION[0], LRNPU_VERSION[1],
                                 self.nce_generation))
        name_enc = self.name.encode("utf-8")
        parts.append(struct.pack(">H", len(name_enc)))
        parts.append(name_enc)

        for section_data in (self.npu_code, self.switch_tables, self.routing_tables):
            parts.append(struct.pack(">I", len(section_data)))
            parts.append(section_data)

        meta_str = "\n".join(f"{k}={v}" for k, v in self.metadata.items()).encode("utf-8")
        parts.append(struct.pack(">I", len(meta_str)))
        parts.append(meta_str)

        payload = b"".join(parts)
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        return payload + struct.pack(">I", crc)


class AOTCompiler:
    """
    Translates an optimised Module into an AOTBinary for a target NCE
    generation.

    The "native instruction lowering" is implemented as a post-processing
    pass over the .lrbs bytecode that:
      1. Expands virtual ISA instructions to concrete NCE micro-ops.
      2. Resolves all SSA references to physical register/channel IDs.
      3. Generates switch programming tables from the WDM channel map.
      4. Bakes routing tables into the binary.
    """

    def __init__(self, nce_generation: int = 1) -> None:
        self.nce_generation = nce_generation

    def compile(self, module: Module) -> AOTBinary:
        """Full AOT compilation of a Module."""
        emitter = BytecodeEmitter()
        lrbs = emitter.emit(module, flags=LRBS_FLAGS_AOT)

        npu_code     = self._lower_to_npu(lrbs, module)
        switch_tables = self._build_switch_tables(module)
        routing_tables = self._build_routing_tables(module)

        binary = AOTBinary(
            name=module.name,
            nce_generation=self.nce_generation,
            npu_code=npu_code,
            switch_tables=switch_tables,
            routing_tables=routing_tables,
            metadata={
                "compiler":   "lightrail-aot-0.1",
                "nce_gen":    str(self.nce_generation),
                "module":     module.name,
                "device_fns": str(len(module.device_functions())),
            },
        )
        return binary

    def make_descriptor(self, binary: AOTBinary, args: list) -> KernelDescriptor:
        """Create a KernelDescriptor ready for Fabric OS dispatch."""
        return KernelDescriptor(
            name=binary.name,
            lrbs_bytes=binary.npu_code,
            routing_info=binary.routing_tables,
            num_tiles=1,
            fabric_generation=binary.nce_generation,
            args=args,
            async_exec=False,
        )

    # -- Internal lowering ---------------------------------------------------

    @staticmethod
    def _lower_to_npu(lrbs: bytes, module: Module) -> bytes:
        """
        Translate .lrbs virtual ISA to NCE native micro-ops.

        In a real compiler this would involve instruction selection,
        register allocation (channel allocation), and peephole opts.
        Here we pass through .lrbs bytes with an NCE header prepended.
        """
        header = struct.pack(">4sHH",
                             b"NCEX",
                             len(module.device_functions()),
                             sum(len(list(f.all_instructions()))
                                 for f in module.device_functions()))
        return header + lrbs

    @staticmethod
    def _build_switch_tables(module: Module) -> bytes:
        """
        Generate WDM switch programming tables.

        Each entry: channel_id (1B) + tile_id (1B) + fabric_layer (1B) + pad (1B)
        """
        parts = []
        for fn in module.device_functions():
            loads = fn.attrs.get("wdm_channel_loads", [])
            for ch_id, load in enumerate(loads):
                if load > 0:
                    tile_id = ch_id % 20
                    layer   = ch_id % 20
                    parts.append(struct.pack(">BBBB", ch_id, tile_id, layer, 0))
        return b"".join(parts)

    @staticmethod
    def _build_routing_tables(module: Module) -> bytes:
        """Serialise per-edge routing paths from the DataflowRouter output."""
        parts = []
        for fn in module.device_functions():
            table = fn.attrs.get("routing_table")
            if table is None:
                continue
            for edge in table.edges:
                route_bytes = bytes(edge.route[:8]).ljust(8, b"\xFF")
                parts.append(struct.pack(">BBd8s",
                                         edge.src_tile & 0xFF,
                                         edge.dst_tile & 0xFF,
                                         edge.latency_ns,
                                         route_bytes))
        return b"".join(parts)

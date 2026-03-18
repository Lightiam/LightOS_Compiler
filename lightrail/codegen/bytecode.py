"""
Stage 5: Tile Bytecode Generator
==================================
Serialises the optimised IR into LightRail Bytecode (.lrbs format).

.lrbs (LightRail Bytecode Stream) is a portable, binary virtual ISA that:
  - Encodes all IR instructions as fixed-width 64-bit words.
  - Embeds WDM channel assignments, tile IDs, and fabric layer routing.
  - Carries ternary/analog layer annotations for photonic-native ops.
  - Is versioned for forward compatibility across fabric generations.

Binary layout:
  LRBS_MAGIC (4 bytes) + VERSION (2 bytes) + FLAGS (2 bytes)
  HEADER section (variable)
  FUNCTION sections (one per device function)
    FUNCTION_HEADER (fixed 32 bytes)
    INSTRUCTION_STREAM (variable: N * 8 bytes)
  ROUTING_TABLE section
  CHECKSUM (4 bytes, CRC32)

Instruction word (64 bits):
  [63:56] opcode      (8 bits)
  [55:48] wdm_channel (8 bits, 0-63)
  [47:40] tile_id     (8 bits)
  [39:32] fabric_layer(8 bits)
  [31:16] result_id   (16 bits, index into SSA name table)
  [15: 0] operand_ids (16 bits packed, up to 2 x 8-bit indices)
"""

from __future__ import annotations
import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from lightrail.ir.ssa import Module, Function, Instruction
from lightrail.ir.ops import Opcode
from lightrail.ir.types import ScalarKind


# ---------------------------------------------------------------------------
# Magic & version
# ---------------------------------------------------------------------------

LRBS_MAGIC   = b"LRBS"
LRBS_VERSION = (0, 1)    # major, minor
LRBS_FLAGS_AOT = 0x0001
LRBS_FLAGS_JIT = 0x0002


# ---------------------------------------------------------------------------
# Opcode encoding (8-bit subset)
# ---------------------------------------------------------------------------

_OP_ENCODING: Dict[Opcode, int] = {
    Opcode.CONST:       0x01,
    Opcode.COPY:        0x02,
    Opcode.IADD:        0x10,
    Opcode.ISUB:        0x11,
    Opcode.IMUL:        0x12,
    Opcode.IDIV:        0x13,
    Opcode.FADD:        0x20,
    Opcode.FSUB:        0x21,
    Opcode.FMUL:        0x22,
    Opcode.FDIV:        0x23,
    Opcode.FMA:         0x24,
    Opcode.FMNA:        0x25,
    Opcode.DOT:         0x26,
    Opcode.MATMUL:      0x27,
    Opcode.LOAD:        0x30,
    Opcode.STORE:       0x31,
    Opcode.DMA_READ:    0x32,
    Opcode.DMA_WRITE:   0x33,
    Opcode.DMA_SYNC:    0x34,
    Opcode.PREFETCH:    0x35,
    Opcode.ALLOC:       0x36,
    Opcode.ALL_REDUCE:  0x40,
    Opcode.ALL_GATHER:  0x41,
    Opcode.REDUCE_SCATTER:0x42,
    Opcode.BROADCAST:   0x43,
    Opcode.P2P_SEND:    0x44,
    Opcode.P2P_RECV:    0x45,
    Opcode.WDM_BIND:    0x50,
    Opcode.WDM_ROUTE:   0x51,
    Opcode.WDM_MUXIN:   0x52,
    Opcode.WDM_DEMUX:   0x53,
    Opcode.TADD:        0x60,
    Opcode.TMUL:        0x61,
    Opcode.TDOT:        0x62,
    Opcode.TERNARY_ENCODE:0x63,
    Opcode.TERNARY_DECODE:0x64,
    Opcode.WAVE_MOD:    0x70,
    Opcode.WAVE_DEMOD:  0x71,
    Opcode.WAVE_PHASE:  0x72,
    Opcode.WAVE_INTERFERE:0x73,
    Opcode.WAVE_ATTENUATE:0x74,
    Opcode.TILE_LOAD:   0x80,
    Opcode.TILE_COMPUTE:0x81,
    Opcode.TILE_STORE:  0x82,
    Opcode.TILE_BARRIER:0x83,
    Opcode.LOOP_BEGIN:  0x84,
    Opcode.LOOP_END:    0x85,
    Opcode.PHI:         0x86,
    Opcode.CAST:        0x87,
    Opcode.QUANTIZE:    0x88,
    Opcode.DEQUANTIZE:  0x89,
    Opcode.ICMP:        0x90,
    Opcode.FCMP:        0x91,
    Opcode.BR:          0xA0,
    Opcode.CBR:         0xA1,
    Opcode.RET:         0xA2,
    Opcode.CALL:        0xA3,
    Opcode.NCE_DISPATCH:0xB0,
    Opcode.FABRIC_SYNC: 0xB1,
    Opcode.DEBUG_PRINT: 0xFF,
}


# ---------------------------------------------------------------------------
# SSA Name → integer ID table
# ---------------------------------------------------------------------------

class NameTable:
    def __init__(self) -> None:
        self._map: Dict[str, int] = {}
        self._counter = 0

    def intern(self, name: str) -> int:
        if name not in self._map:
            self._map[name] = self._counter
            self._counter += 1
        return self._map[name]

    def id_of(self, name: str) -> int:
        return self._map.get(name, 0xFFFF)

    def serialise(self) -> bytes:
        """Serialise the name table as a length-prefixed string pool."""
        entries = sorted(self._map.items(), key=lambda kv: kv[1])
        parts = []
        for name, idx in entries:
            enc = name.encode("utf-8")
            parts.append(struct.pack(">HH", idx, len(enc)))
            parts.append(enc)
        return b"".join(parts)


# ---------------------------------------------------------------------------
# Bytecode Emitter
# ---------------------------------------------------------------------------

@dataclass
class LRBSFile:
    """In-memory representation of a .lrbs file before serialisation."""
    module_name: str
    flags: int = 0
    functions: List[bytes] = field(default_factory=list)
    name_table_bytes: bytes = b""
    routing_bytes: bytes = b""
    metadata: Dict[str, str] = field(default_factory=dict)


class BytecodeEmitter:
    """
    Converts a post-optimisation Module into an LRBSFile and serialises it
    to bytes.
    """

    def emit(self, module: Module, flags: int = LRBS_FLAGS_JIT) -> bytes:
        lrbs = LRBSFile(module_name=module.name, flags=flags)
        names = NameTable()

        # Emit each device function
        for fn in module.device_functions():
            fn_bytes = self._emit_function(fn, names)
            lrbs.functions.append(fn_bytes)

        lrbs.name_table_bytes = names.serialise()
        lrbs.routing_bytes    = self._emit_routing(module)
        lrbs.metadata["compiler"] = "lightrail-compiler-0.1"
        lrbs.metadata["target"]   = "lightrail-nce-gen1"

        return self._serialise(lrbs)

    def _emit_function(self, fn: Function, names: NameTable) -> bytes:
        parts = []

        # Function header: name_len(2) + name + param_count(2) + return_type(1)
        fn_name_enc = fn.name.encode("utf-8")
        parts.append(struct.pack(">HH", len(fn_name_enc), len(fn.params)))
        parts.append(fn_name_enc)
        parts.append(struct.pack(">B", 0x01 if fn.is_device else 0x00))

        # Instruction stream
        for instr in fn.all_instructions():
            word = self._encode_instruction(instr, names)
            parts.append(struct.pack(">Q", word))  # 8-byte big-endian

        # End-of-function sentinel
        parts.append(struct.pack(">Q", 0xDEADC0DEDEADC0DE))

        return b"".join(parts)

    def _encode_instruction(self, instr: Instruction, names: NameTable) -> int:
        """Pack one instruction into a 64-bit word."""
        op_byte     = _OP_ENCODING.get(instr.op, 0xFE) & 0xFF
        ch_byte     = instr.attrs.get("wdm_channel", 0) & 0xFF
        tile_byte   = instr.attrs.get("tile_id", 0) & 0xFF
        layer_byte  = instr.attrs.get("fabric_layer", 0) & 0xFF

        result_id   = names.intern(instr.result) if instr.result else 0xFFFF
        result_id  &= 0xFFFF

        # Pack first two operand IDs into 16 bits (8 bits each, truncated)
        op0 = names.intern(instr.operands[0]) & 0xFF if len(instr.operands) > 0 else 0xFF
        op1 = names.intern(instr.operands[1]) & 0xFF if len(instr.operands) > 1 else 0xFF
        operand_word = (op0 << 8) | op1

        word = (
            (op_byte     << 56) |
            (ch_byte     << 48) |
            (tile_byte   << 40) |
            (layer_byte  << 32) |
            (result_id   << 16) |
            operand_word
        )
        return word

    def _emit_routing(self, module: Module) -> bytes:
        """Serialise routing tables from all device functions."""
        parts = []
        for fn in module.device_functions():
            table = fn.attrs.get("routing_table")
            if table is None:
                continue
            for edge in table.edges:
                route_bytes = bytes(edge.route[:8])  # max 8 layer hops
                route_bytes = route_bytes.ljust(8, b"\xFF")
                parts.append(struct.pack(
                    ">BBBBd8s",
                    edge.src_tile & 0xFF,
                    edge.dst_tile & 0xFF,
                    edge.src_layer & 0xFF,
                    edge.dst_layer & 0xFF,
                    edge.latency_ns,
                    route_bytes,
                ))
        return b"".join(parts)

    def _serialise(self, lrbs: LRBSFile) -> bytes:
        parts = []

        # Magic + version + flags
        parts.append(LRBS_MAGIC)
        parts.append(struct.pack(">BBH", LRBS_VERSION[0], LRBS_VERSION[1], lrbs.flags))

        # Module name
        name_enc = lrbs.module_name.encode("utf-8")
        parts.append(struct.pack(">H", len(name_enc)))
        parts.append(name_enc)

        # Function count + function blocks
        parts.append(struct.pack(">H", len(lrbs.functions)))
        for fn_bytes in lrbs.functions:
            parts.append(struct.pack(">I", len(fn_bytes)))
            parts.append(fn_bytes)

        # Name table
        parts.append(struct.pack(">I", len(lrbs.name_table_bytes)))
        parts.append(lrbs.name_table_bytes)

        # Routing table
        parts.append(struct.pack(">I", len(lrbs.routing_bytes)))
        parts.append(lrbs.routing_bytes)

        # Metadata (key=value pairs)
        meta_str = "\n".join(f"{k}={v}" for k, v in lrbs.metadata.items()).encode("utf-8")
        parts.append(struct.pack(">I", len(meta_str)))
        parts.append(meta_str)

        payload = b"".join(parts)
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        return payload + struct.pack(">I", crc)

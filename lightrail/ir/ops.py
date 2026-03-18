"""
LightRail IR Operations
=======================
Defines the opcode enum and Instruction dataclass for the SSA IR.
Covers arithmetic, memory, control flow, photonic collectives, and
LightRail-specific operations like wavelength binding and ternary compute.
"""

from __future__ import annotations
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, List, Optional


class Opcode(Enum):
    # -----------------------------------------------------------------------
    # Constants & Identity
    # -----------------------------------------------------------------------
    CONST       = auto()   # constant literal
    UNDEF       = auto()   # undefined value (poison)
    COPY        = auto()   # SSA copy / register rename

    # -----------------------------------------------------------------------
    # Arithmetic (integer)
    # -----------------------------------------------------------------------
    IADD        = auto()
    ISUB        = auto()
    IMUL        = auto()
    IDIV        = auto()
    IMOD        = auto()
    INEG        = auto()
    IAND        = auto()
    IOR         = auto()
    IXOR        = auto()
    INOT        = auto()
    ISHL        = auto()
    ISHR        = auto()
    IUSHR       = auto()

    # -----------------------------------------------------------------------
    # Arithmetic (float)
    # -----------------------------------------------------------------------
    FADD        = auto()
    FSUB        = auto()
    FMUL        = auto()
    FDIV        = auto()
    FNEG        = auto()
    FABS        = auto()
    FSQRT       = auto()
    FEXP        = auto()
    FLOG        = auto()
    FSIN        = auto()
    FCOS        = auto()

    # -----------------------------------------------------------------------
    # Fused Operations (photonic-friendly single-step)
    # -----------------------------------------------------------------------
    FMA         = auto()   # a * b + c  (fused multiply-add)
    FMNA        = auto()   # -(a * b) + c
    DOT         = auto()   # inner product of two vectors
    MATMUL      = auto()   # tiled matrix multiply

    # -----------------------------------------------------------------------
    # Comparisons
    # -----------------------------------------------------------------------
    ICMP        = auto()   # integer compare (predicate in attr)
    FCMP        = auto()   # float compare

    # -----------------------------------------------------------------------
    # Type Conversions
    # -----------------------------------------------------------------------
    CAST        = auto()   # generic bitcast / numeric cast
    QUANTIZE    = auto()   # float -> low-precision (FP8, ABFP16, TERNARY)
    DEQUANTIZE  = auto()   # low-precision -> float

    # -----------------------------------------------------------------------
    # Memory
    # -----------------------------------------------------------------------
    ALLOC       = auto()   # allocate SRAM buffer
    LOAD        = auto()   # load from address
    STORE       = auto()   # store to address
    DMA_READ    = auto()   # async DMA: remote chip SRAM -> local SRAM
    DMA_WRITE   = auto()   # async DMA: local SRAM -> remote chip SRAM
    DMA_SYNC    = auto()   # barrier: wait for in-flight DMA ops
    PREFETCH    = auto()   # hint: begin DMA before data is needed

    # -----------------------------------------------------------------------
    # Control Flow
    # -----------------------------------------------------------------------
    BR          = auto()   # unconditional branch
    CBR         = auto()   # conditional branch
    RET         = auto()   # return from function
    CALL        = auto()   # function call
    LOOP_BEGIN  = auto()   # loop header marker
    LOOP_END    = auto()   # loop footer marker
    PHI         = auto()   # SSA phi node

    # -----------------------------------------------------------------------
    # Photonic Collectives (intercepted by Fabric OS router)
    # -----------------------------------------------------------------------
    ALL_REDUCE  = auto()   # fabric-wide all-reduce
    ALL_GATHER  = auto()   # fabric-wide all-gather
    REDUCE_SCATTER = auto()
    BROADCAST   = auto()   # 1-to-N optical broadcast
    P2P_SEND    = auto()   # point-to-point optical send
    P2P_RECV    = auto()   # point-to-point optical receive

    # -----------------------------------------------------------------------
    # Wavelength / WDM Operations (Stage 4)
    # -----------------------------------------------------------------------
    WDM_BIND    = auto()   # bind task to wavelength channel
    WDM_ROUTE   = auto()   # route data through WDM switch
    WDM_MUXIN   = auto()   # multiplex signal onto channel
    WDM_DEMUX   = auto()   # demultiplex signal from channel

    # -----------------------------------------------------------------------
    # Ternary Compute (Layers 1-5)
    # -----------------------------------------------------------------------
    TADD        = auto()   # ternary add (saturating)
    TMUL        = auto()   # ternary multiply
    TDOT        = auto()   # ternary dot product
    TERNARY_ENCODE  = auto()  # float -> ternary
    TERNARY_DECODE  = auto()  # ternary -> float

    # -----------------------------------------------------------------------
    # Analog Wave Compute (Layers 6 & 7)
    # -----------------------------------------------------------------------
    WAVE_MOD    = auto()   # amplitude modulation
    WAVE_DEMOD  = auto()   # demodulation / detection
    WAVE_PHASE  = auto()   # phase shift operation
    WAVE_INTERFERE = auto()  # optical interference (add amplitudes)
    WAVE_ATTENUATE = auto()  # apply attenuation mask

    # -----------------------------------------------------------------------
    # Tiling / Pipeline Markers (software pipelining)
    # -----------------------------------------------------------------------
    TILE_LOAD   = auto()   # DMA load of a tile into SRAM
    TILE_COMPUTE = auto()  # compute phase over tile
    TILE_STORE  = auto()   # store tile result to fabric memory
    TILE_BARRIER = auto()  # synchronise tile pipeline stages

    # -----------------------------------------------------------------------
    # Intrinsics / Fabric OS Interface
    # -----------------------------------------------------------------------
    FABRIC_SYNC  = auto()  # global fabric barrier
    NCE_DISPATCH = auto()  # dispatch kernel to NCE
    DEBUG_PRINT  = auto()  # debug sink (eliminated in AOT)


@dataclass
class Instruction:
    """
    A single SSA instruction in the LightRail IR.

    Fields:
        op      : Opcode
        result  : Optional SSA value name (None for side-effect-only ops)
        operands: List of SSA value names consumed by this instruction
        attrs   : Opcode-specific attributes (predicate, dtype, shape, etc.)
        type_   : Result type (None for void ops)
        metadata: Optional source location / debug info
    """
    op:       Opcode
    result:   Optional[str]
    operands: List[str]
    attrs:    dict[str, Any] = field(default_factory=dict)
    type_:    Any = None          # LRType | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_terminator(self) -> bool:
        return self.op in {Opcode.BR, Opcode.CBR, Opcode.RET}

    def is_pure(self) -> bool:
        """Pure if no side effects (memory writes, DMA, collectives, etc.)."""
        impure = {
            Opcode.STORE, Opcode.DMA_READ, Opcode.DMA_WRITE,
            Opcode.DMA_SYNC, Opcode.P2P_SEND, Opcode.P2P_RECV,
            Opcode.ALL_REDUCE, Opcode.ALL_GATHER, Opcode.REDUCE_SCATTER,
            Opcode.BROADCAST, Opcode.FABRIC_SYNC, Opcode.NCE_DISPATCH,
            Opcode.DEBUG_PRINT, Opcode.TILE_BARRIER,
        }
        return self.op not in impure

    def __repr__(self) -> str:
        res = f"%{self.result} = " if self.result else ""
        ops = ", ".join(f"%{o}" for o in self.operands)
        attrs_str = ""
        if self.attrs:
            attrs_str = " {" + ", ".join(f"{k}={v}" for k, v in self.attrs.items()) + "}"
        type_str = f" : {self.type_}" if self.type_ else ""
        return f"{res}{self.op.name}({ops}){attrs_str}{type_str}"

"""
LightRail Type System
=====================
Defines all scalar, vector, and LightRail-specific types used throughout the IR,
including standard numeric types, low-precision formats, and photonic-native types
such as Ternary (-1, 0, +1) and Analog Wave Compute.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Base Type ABC
# ---------------------------------------------------------------------------

class LRType:
    """Abstract base for all LightRail types."""

    def bitwidth(self) -> int:
        raise NotImplementedError

    def is_numeric(self) -> bool:
        return False

    def is_photonic(self) -> bool:
        return False

    def __repr__(self) -> str:
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# Scalar Numeric Types
# ---------------------------------------------------------------------------

class ScalarKind(Enum):
    BOOL    = auto()
    INT8    = auto()
    INT16   = auto()
    INT32   = auto()
    INT64   = auto()
    UINT8   = auto()
    UINT16  = auto()
    UINT32  = auto()
    UINT64  = auto()
    FP16    = auto()
    BF16    = auto()
    FP32    = auto()
    FP64    = auto()
    # LightRail low-precision formats
    FP8     = auto()   # 8-bit float (E4M3 or E5M2)
    ABFP16  = auto()   # Adaptive Block Floating Point 16
    # Photonic-native
    TERNARY = auto()   # {-1, 0, +1} mapped to optical power levels
    ANALOG  = auto()   # Continuous analog wave value


_SCALAR_BITWIDTHS: dict[ScalarKind, int] = {
    ScalarKind.BOOL:    1,
    ScalarKind.INT8:    8,
    ScalarKind.INT16:   16,
    ScalarKind.INT32:   32,
    ScalarKind.INT64:   64,
    ScalarKind.UINT8:   8,
    ScalarKind.UINT16:  16,
    ScalarKind.UINT32:  32,
    ScalarKind.UINT64:  64,
    ScalarKind.FP16:    16,
    ScalarKind.BF16:    16,
    ScalarKind.FP32:    32,
    ScalarKind.FP64:    64,
    ScalarKind.FP8:     8,
    ScalarKind.ABFP16:  16,
    ScalarKind.TERNARY: 2,   # 2 bits to represent {-1, 0, +1}
    ScalarKind.ANALOG:  32,  # stored as FP32 envelope amplitude
}


@dataclass(frozen=True)
class ScalarType(LRType):
    kind: ScalarKind

    def bitwidth(self) -> int:
        return _SCALAR_BITWIDTHS[self.kind]

    def is_numeric(self) -> bool:
        return True

    def is_integer(self) -> bool:
        return self.kind in {
            ScalarKind.BOOL, ScalarKind.INT8, ScalarKind.INT16,
            ScalarKind.INT32, ScalarKind.INT64, ScalarKind.UINT8,
            ScalarKind.UINT16, ScalarKind.UINT32, ScalarKind.UINT64,
        }

    def is_float(self) -> bool:
        return self.kind in {
            ScalarKind.FP8, ScalarKind.FP16, ScalarKind.BF16,
            ScalarKind.ABFP16, ScalarKind.FP32, ScalarKind.FP64,
        }

    def is_photonic(self) -> bool:
        return self.kind in {ScalarKind.TERNARY, ScalarKind.ANALOG}

    def __repr__(self) -> str:
        return self.kind.name.lower()


# ---------------------------------------------------------------------------
# Vector / Tensor Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VectorType(LRType):
    """Fixed-length SIMD vector on a single optical channel."""
    element: ScalarType
    lanes: int  # e.g., 8, 16, 32, 64

    def bitwidth(self) -> int:
        return self.element.bitwidth() * self.lanes

    def is_numeric(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"<{self.lanes} x {self.element}>"


@dataclass(frozen=True)
class TensorType(LRType):
    """Multi-dimensional tensor routed across optical fabric tiles."""
    element: ScalarType
    shape: Tuple[int, ...]
    layout: str = "row_major"  # or "col_major", "tiled"

    def bitwidth(self) -> int:
        n = 1
        for d in self.shape:
            n *= d
        return n * self.element.bitwidth()

    def is_numeric(self) -> bool:
        return True

    def num_elements(self) -> int:
        n = 1
        for d in self.shape:
            n *= d
        return n

    def __repr__(self) -> str:
        dims = "x".join(str(d) for d in self.shape)
        return f"tensor<{dims}, {self.element}>"


# ---------------------------------------------------------------------------
# Pointer / Memory Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PointerType(LRType):
    """Pointer into the flat, fabric-unified address space."""
    pointee: LRType
    address_space: str = "fabric"  # "fabric" | "sram" | "host"

    def bitwidth(self) -> int:
        return 64  # 64-bit fabric addresses

    def __repr__(self) -> str:
        return f"ptr<{self.address_space}, {self.pointee}>"


# ---------------------------------------------------------------------------
# Optical-Specific Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WavelengthChannelType(LRType):
    """
    A logical type representing a bound WDM channel.
    'channel_id' is 0-63 (64 virtual processors via wavelength division).
    """
    channel_id: int  # 0 .. 63

    def bitwidth(self) -> int:
        return 6  # 6 bits to index 64 channels

    def is_photonic(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"wdm_ch<{self.channel_id}>"


@dataclass(frozen=True)
class TernaryVectorType(LRType):
    """
    A native ternary vector for LightRail Layers 1-5 compute.
    Values in {-1, 0, +1} corresponding to optical power levels.
    """
    lanes: int

    def bitwidth(self) -> int:
        return self.lanes * 2

    def is_photonic(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"ternary<{self.lanes}>"


@dataclass(frozen=True)
class AnalogWaveType(LRType):
    """
    Analog wave compute type for LightRail Layers 6 & 7.
    Represents a continuous-amplitude optical signal.
    """
    frequency_hz: float = 193.1e12  # default ~1550 nm C-band
    lanes: int = 1

    def bitwidth(self) -> int:
        return self.lanes * 32  # stored as FP32 amplitude envelope

    def is_photonic(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"analog_wave<{self.lanes}>"


# ---------------------------------------------------------------------------
# Function / Void Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VoidType(LRType):
    def bitwidth(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "void"


@dataclass(frozen=True)
class FunctionType(LRType):
    params: Tuple[LRType, ...]
    ret: LRType

    def bitwidth(self) -> int:
        return 64  # function pointer

    def __repr__(self) -> str:
        params_str = ", ".join(repr(p) for p in self.params)
        return f"fn({params_str}) -> {self.ret}"


# ---------------------------------------------------------------------------
# Convenience singletons
# ---------------------------------------------------------------------------

VOID    = VoidType()
BOOL    = ScalarType(ScalarKind.BOOL)
INT8    = ScalarType(ScalarKind.INT8)
INT16   = ScalarType(ScalarKind.INT16)
INT32   = ScalarType(ScalarKind.INT32)
INT64   = ScalarType(ScalarKind.INT64)
UINT8   = ScalarType(ScalarKind.UINT8)
UINT16  = ScalarType(ScalarKind.UINT16)
UINT32  = ScalarType(ScalarKind.UINT32)
UINT64  = ScalarType(ScalarKind.UINT64)
FP8     = ScalarType(ScalarKind.FP8)
FP16    = ScalarType(ScalarKind.FP16)
BF16    = ScalarType(ScalarKind.BF16)
ABFP16  = ScalarType(ScalarKind.ABFP16)
FP32    = ScalarType(ScalarKind.FP32)
FP64    = ScalarType(ScalarKind.FP64)
TERNARY = ScalarType(ScalarKind.TERNARY)
ANALOG  = ScalarType(ScalarKind.ANALOG)


def python_type_to_lr(py_type: type) -> LRType:
    """Best-effort mapping from Python built-in types to LightRail types."""
    mapping: dict[type, LRType] = {
        bool:  BOOL,
        int:   INT32,
        float: FP32,
    }
    return mapping.get(py_type, INT32)


def infer_from_annotation(annotation: str) -> LRType:
    """Parse a string annotation like 'float32' or 'int8' into an LRType."""
    table: dict[str, LRType] = {
        "bool":    BOOL,
        "int8":    INT8,   "i8":   INT8,
        "int16":   INT16,  "i16":  INT16,
        "int32":   INT32,  "i32":  INT32,
        "int64":   INT64,  "i64":  INT64,
        "uint8":   UINT8,  "u8":   UINT8,
        "uint32":  UINT32, "u32":  UINT32,
        "float8":  FP8,    "fp8":  FP8,
        "float16": FP16,   "fp16": FP16,
        "bfloat16":BF16,   "bf16": BF16,
        "abfp16":  ABFP16,
        "float32": FP32,   "fp32": FP32,  "float": FP32,
        "float64": FP64,   "fp64": FP64,  "double": FP64,
        "ternary": TERNARY,
        "analog":  ANALOG,
        "void":    VOID,
    }
    return table.get(annotation.strip().lower(), FP32)

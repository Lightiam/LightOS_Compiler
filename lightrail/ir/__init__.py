"""LightRail IR package."""
from lightrail.ir.types import (
    LRType, ScalarType, ScalarKind, VectorType, TensorType,
    PointerType, WavelengthChannelType, TernaryVectorType, AnalogWaveType,
    VoidType, FunctionType,
    VOID, BOOL, INT8, INT16, INT32, INT64, UINT8, UINT16, UINT32, UINT64,
    FP8, FP16, BF16, ABFP16, FP32, FP64, TERNARY, ANALOG,
    python_type_to_lr, infer_from_annotation,
)
from lightrail.ir.ops import Opcode, Instruction
from lightrail.ir.ssa import BasicBlock, Function, Module, Builder, ValueTable

__all__ = [
    "LRType", "ScalarType", "ScalarKind", "VectorType", "TensorType",
    "PointerType", "WavelengthChannelType", "TernaryVectorType", "AnalogWaveType",
    "VoidType", "FunctionType",
    "VOID", "BOOL", "INT8", "INT16", "INT32", "INT64",
    "UINT8", "UINT16", "UINT32", "UINT64",
    "FP8", "FP16", "BF16", "ABFP16", "FP32", "FP64", "TERNARY", "ANALOG",
    "python_type_to_lr", "infer_from_annotation",
    "Opcode", "Instruction",
    "BasicBlock", "Function", "Module", "Builder", "ValueTable",
]

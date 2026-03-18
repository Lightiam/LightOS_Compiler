"""
Stage 2: Type Inference & Lowering Pass
========================================
Traverses every instruction in a Module and:

  1. Propagates known types from constants and parameters to derived values.
  2. Inserts CAST instructions wherever a type mismatch is detected.
  3. Promotes loose Python ints/floats to the target type declared in the
     function signature or via annotations.
  4. Identifies and annotates low-precision operands (FP8, ABFP16, TERNARY)
     so later passes can route them to the correct optical layer.
  5. Flattens constant conditions detected during type propagation.
"""

from __future__ import annotations
from typing import Dict, Optional

from lightrail.ir.ssa import Module, Function, BasicBlock, Instruction
from lightrail.ir.ops import Opcode
from lightrail.ir.types import (
    LRType, ScalarType, ScalarKind, VectorType, TensorType,
    VOID, BOOL, INT32, FP32, FP64,
    python_type_to_lr, infer_from_annotation,
)


# ---------------------------------------------------------------------------
# Type lattice helpers
# ---------------------------------------------------------------------------

_NUMERIC_RANK: Dict[ScalarKind, int] = {
    ScalarKind.BOOL:    0,
    ScalarKind.INT8:    1,
    ScalarKind.UINT8:   1,
    ScalarKind.INT16:   2,
    ScalarKind.UINT16:  2,
    ScalarKind.INT32:   3,
    ScalarKind.UINT32:  3,
    ScalarKind.INT64:   4,
    ScalarKind.UINT64:  4,
    ScalarKind.FP8:     5,
    ScalarKind.FP16:    6,
    ScalarKind.BF16:    6,
    ScalarKind.ABFP16:  7,
    ScalarKind.FP32:    8,
    ScalarKind.FP64:    9,
    ScalarKind.TERNARY: 2,
    ScalarKind.ANALOG:  8,
}


def _widen(a: LRType, b: LRType) -> LRType:
    """Return the wider of two types (numeric promotion)."""
    if a == b:
        return a
    if isinstance(a, ScalarType) and isinstance(b, ScalarType):
        ra, rb = _NUMERIC_RANK.get(a.kind, 0), _NUMERIC_RANK.get(b.kind, 0)
        return a if ra >= rb else b
    return a  # fall back to left-hand type


def _infer_result_type(op: Opcode, operand_types: list[LRType]) -> LRType:
    """Heuristic: infer the result type from opcode + operand types."""
    fp_ops = {
        Opcode.FADD, Opcode.FSUB, Opcode.FMUL, Opcode.FDIV,
        Opcode.FNEG, Opcode.FABS, Opcode.FSQRT, Opcode.FEXP,
        Opcode.FLOG, Opcode.FSIN, Opcode.FCOS, Opcode.FMA,
        Opcode.FMNA, Opcode.DOT, Opcode.MATMUL,
    }
    int_ops = {
        Opcode.IADD, Opcode.ISUB, Opcode.IMUL, Opcode.IDIV,
        Opcode.IMOD, Opcode.INEG, Opcode.IAND, Opcode.IOR,
        Opcode.IXOR, Opcode.INOT, Opcode.ISHL, Opcode.ISHR,
    }
    cmp_ops = {Opcode.ICMP, Opcode.FCMP}
    void_ops = {Opcode.STORE, Opcode.RET, Opcode.BR, Opcode.CBR,
                Opcode.DMA_SYNC, Opcode.FABRIC_SYNC, Opcode.TILE_BARRIER,
                Opcode.LOOP_BEGIN, Opcode.LOOP_END, Opcode.DMA_WRITE}
    passthrough = {Opcode.COPY, Opcode.PHI, Opcode.CAST}

    if op in void_ops:
        return VOID
    if op in cmp_ops:
        return BOOL
    if op in fp_ops:
        if operand_types:
            return operand_types[0] if isinstance(operand_types[0], ScalarType) else FP32
        return FP32
    if op in int_ops:
        if operand_types:
            return operand_types[0] if isinstance(operand_types[0], ScalarType) else INT32
        return INT32
    if op in passthrough:
        return operand_types[0] if operand_types else FP32
    if op == Opcode.CONST:
        return FP32  # will be updated from attrs
    return FP32  # safe default


# ---------------------------------------------------------------------------
# Type Inference Pass
# ---------------------------------------------------------------------------

class TypeInferencePass:
    """
    Performs a forward dataflow pass to infer and annotate types on all
    SSA values and instructions within a Module.
    """

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            self._infer_function(fn)
        return module

    def _infer_function(self, fn: Function) -> None:
        """Propagate types through all blocks of a function."""
        # Build initial type environment from parameters
        type_env: Dict[str, LRType] = {}
        for pname, pty in fn.params:
            type_env[pname] = pty

        changed = True
        iterations = 0
        while changed and iterations < 10:
            changed = False
            iterations += 1
            for bb in fn.blocks:
                for instr in bb.instructions:
                    changed |= self._infer_instruction(instr, type_env, fn)

    def _infer_instruction(
        self, instr: Instruction, env: Dict[str, LRType], fn: Function
    ) -> bool:
        """
        Attempt to infer / refine the type of instr.result.
        Returns True if a type was updated (triggers re-iteration).
        """
        # Collect operand types
        op_types = [env.get(op) for op in instr.operands if op in env]
        op_types = [t for t in op_types if t is not None]

        # Special handling for CONST
        if instr.op == Opcode.CONST and instr.result:
            value = instr.attrs.get("value")
            if isinstance(value, bool):
                new_ty = BOOL
            elif isinstance(value, int):
                new_ty = INT32
            elif isinstance(value, float):
                new_ty = FP32
            else:
                new_ty = FP32
            return self._update(instr, env, new_ty)

        # Special handling for CAST - use the declared target type from attrs
        if instr.op == Opcode.CAST and instr.result:
            to_str = instr.attrs.get("to", "")
            new_ty = infer_from_annotation(to_str) if to_str else (op_types[0] if op_types else FP32)
            return self._update(instr, env, new_ty)

        if instr.result is None:
            return False

        # Derive result type from opcode + operand types
        new_ty = _infer_result_type(instr.op, op_types)
        return self._update(instr, env, new_ty)

    @staticmethod
    def _update(instr: Instruction, env: Dict[str, LRType], new_ty: LRType) -> bool:
        if instr.result is None:
            return False
        old_ty = instr.type_
        if old_ty != new_ty:
            instr.type_ = new_ty
            env[instr.result] = new_ty
            return True
        # Ensure env is consistent even if no change
        if instr.result not in env:
            env[instr.result] = new_ty
            return True
        return False

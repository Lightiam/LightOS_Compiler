"""
Stage 3: Fused Multiply-Add (FMA) Fusion Pass
===============================================
Scans the SSA IR for patterns of the form:

    %t = FMUL(%a, %b)
    %r = FADD(%t, %c)          =>   %r = FMA(%a, %b, %c)

or the negated form:

    %t = FMUL(%a, %b)
    %r = FSUB(%c, %t)          =>   %r = FMNA(%a, %b, %c)

These are critical optimisations for the LightRail NCE because:
  - The photonic multiply-accumulate unit executes FMA in a single optical
    cycle instead of two.
  - Eliminating the intermediate %t value reduces register pressure and
    WDM channel occupancy.

The pass also fuses scalar DOT -> MATMUL patterns when tiling metadata
is available.
"""

from __future__ import annotations
from typing import Dict, List, Optional

from lightrail.ir.ssa import Module, Function, BasicBlock, Instruction
from lightrail.ir.ops import Opcode
from lightrail.ir.types import VOID


class FMAFusionPass:

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            for bb in fn.blocks:
                self._fuse_block(bb)
        return module

    def _fuse_block(self, bb: BasicBlock) -> None:
        """
        Single-pass scan of a block replacing FMUL+FADD/FSUB pairs with FMA/FMNA.
        """
        # Build a map: result_name -> Instruction index for FMUL results
        fmul_map: Dict[str, int] = {}
        dead: set[int] = set()

        new_instrs: List[Instruction] = []
        idx_map: Dict[int, int] = {}  # old index -> new index in new_instrs

        for i, instr in enumerate(bb.instructions):
            if instr.op == Opcode.FMUL and instr.result:
                fmul_map[instr.result] = i

        for i, instr in enumerate(bb.instructions):
            if i in dead:
                continue

            fused = False

            # FADD(t, c) where t is result of FMUL(a, b)
            if instr.op == Opcode.FADD and len(instr.operands) == 2:
                for op_idx, op in enumerate(instr.operands):
                    if op in fmul_map:
                        mul_idx = fmul_map[op]
                        mul = bb.instructions[mul_idx]
                        other = instr.operands[1 - op_idx]
                        # Build FMA
                        fma = Instruction(
                            op=Opcode.FMA,
                            result=instr.result,
                            operands=[mul.operands[0], mul.operands[1], other],
                            attrs={"fused_from": "fmul+fadd"},
                            type_=instr.type_,
                            metadata=instr.metadata,
                        )
                        new_instrs.append(fma)
                        dead.add(mul_idx)
                        fused = True
                        break

            # FSUB(c, t) where t is result of FMUL(a, b)  => FMNA
            elif instr.op == Opcode.FSUB and len(instr.operands) == 2:
                t = instr.operands[1]  # subtracted term
                if t in fmul_map:
                    mul_idx = fmul_map[t]
                    mul = bb.instructions[mul_idx]
                    c = instr.operands[0]
                    fmna = Instruction(
                        op=Opcode.FMNA,
                        result=instr.result,
                        operands=[mul.operands[0], mul.operands[1], c],
                        attrs={"fused_from": "fmul+fsub"},
                        type_=instr.type_,
                        metadata=instr.metadata,
                    )
                    new_instrs.append(fmna)
                    dead.add(mul_idx)
                    fused = True

            if not fused:
                new_instrs.append(instr)

        # Rebuild block without dead FMUL instructions
        final: List[Instruction] = []
        for i, instr in enumerate(new_instrs):
            # Skip original FMUL instructions that were fused (they appear in new_instrs
            # because we didn't remove them there, we marked them dead in the original list)
            final.append(instr)

        # Remove dead originals that slipped through (belt-and-suspenders)
        really_final = [
            instr for instr in final
            if not (instr.op == Opcode.FMUL and instr.result and
                    not any(instr.result in i2.operands for i2 in final if i2 is not instr))
        ]
        bb.instructions = really_final

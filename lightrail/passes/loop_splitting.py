"""
Stage 3: Loop Splitting Pass
==============================
Splits monolithic loop bodies into three canonical pipeline stages:

    TILE_LOAD -> TILE_COMPUTE -> TILE_STORE

This transforms a naive loop:

    for i in range(N):
        x = load(A, i)
        y = compute(x)
        store(B, i, y)

Into an explicitly pipelined form that the DMA prefetch scheduler can
exploit.  The pass:

  1. Identifies basic blocks annotated with LOOP_BEGIN / LOOP_END markers.
  2. Classifies instructions within the body as Load, Compute, or Store phase.
  3. Wraps each group with TILE_LOAD / TILE_COMPUTE / TILE_STORE markers.
  4. Inserts PREFETCH hints ahead of TILE_LOAD ops (software pipelining).
  5. Removes the manual prologue/epilogue burden from the developer.
"""

from __future__ import annotations
from typing import List, Tuple

from lightrail.ir.ssa import Module, Function, BasicBlock, Instruction
from lightrail.ir.ops import Opcode
from lightrail.ir.types import VOID


def _classify(instr: Instruction) -> str:
    """Classify an instruction as 'load', 'store', or 'compute'."""
    load_ops  = {Opcode.LOAD, Opcode.DMA_READ, Opcode.TILE_LOAD}
    store_ops = {Opcode.STORE, Opcode.DMA_WRITE, Opcode.TILE_STORE}
    if instr.op in load_ops:
        return "load"
    if instr.op in store_ops:
        return "store"
    if instr.op in {Opcode.LOOP_BEGIN, Opcode.LOOP_END,
                    Opcode.PHI, Opcode.BR, Opcode.CBR, Opcode.RET}:
        return "ctrl"
    return "compute"


def _wrap(instrs: List[Instruction], begin_op: Opcode, end_op: Opcode) -> List[Instruction]:
    if not instrs:
        return []
    begin = Instruction(op=begin_op, result=None, operands=[], type_=VOID)
    end   = Instruction(op=end_op,   result=None, operands=[], type_=VOID)
    return [begin] + instrs + [end]


class LoopSplittingPass:
    """
    Inserts tile pipeline stage markers around loop bodies, enabling the
    DMA prefetch scheduler to pipeline loads with computation.
    """

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            self._process_function(fn)
        return module

    def _process_function(self, fn: Function) -> None:
        # Find loop body blocks (between LOOP_BEGIN and LOOP_END markers)
        for bb in fn.blocks:
            self._split_block(bb)

    def _split_block(self, bb: BasicBlock) -> None:
        """
        If the block contains a LOOP_BEGIN..LOOP_END pair, split the body
        instructions into load / compute / store phases with markers.
        """
        has_loop = any(
            i.op in {Opcode.LOOP_BEGIN, Opcode.LOOP_END}
            for i in bb.instructions
        )
        if not has_loop:
            return

        ctrl:    List[Instruction] = []
        loads:   List[Instruction] = []
        computes: List[Instruction] = []
        stores:  List[Instruction] = []

        in_loop = False
        for instr in bb.instructions:
            if instr.op == Opcode.LOOP_BEGIN:
                ctrl.append(instr)
                in_loop = True
                continue
            if instr.op == Opcode.LOOP_END:
                in_loop = False
                continue
            if not in_loop:
                ctrl.append(instr)
                continue

            kind = _classify(instr)
            if kind == "load":
                loads.append(instr)
            elif kind == "store":
                stores.append(instr)
            elif kind == "ctrl":
                ctrl.append(instr)
            else:
                computes.append(instr)

        if not (loads or computes or stores):
            return  # nothing to split

        # Insert PREFETCH hints before loads (software pipeline)
        prefetch_hints: List[Instruction] = []
        for ld in loads:
            if ld.op == Opcode.LOAD and ld.operands:
                prefetch_hints.append(
                    Instruction(
                        op=Opcode.PREFETCH,
                        result=None,
                        operands=ld.operands[:],
                        attrs={"distance": 2},
                        type_=VOID,
                    )
                )

        # Rebuild block
        new_instrs: List[Instruction] = []
        new_instrs.extend(ctrl)
        new_instrs.extend(prefetch_hints)
        new_instrs.extend(_wrap(loads,    Opcode.TILE_LOAD,    Opcode.TILE_BARRIER))
        new_instrs.extend(_wrap(computes, Opcode.TILE_COMPUTE, Opcode.TILE_BARRIER))
        new_instrs.extend(_wrap(stores,   Opcode.TILE_STORE,   Opcode.TILE_BARRIER))

        # Append loop end marker
        new_instrs.append(
            Instruction(op=Opcode.LOOP_END, result=None, operands=[], type_=VOID)
        )

        bb.instructions = new_instrs

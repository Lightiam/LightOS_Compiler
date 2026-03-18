"""
Dead Code Elimination (DCE) Pass
==================================
Removes SSA instructions whose results are never used and which have no
side effects (pure instructions only, per Instruction.is_pure()).

Algorithm: classic mark-and-sweep over the def-use graph.
  1. Collect all "live" SSA names referenced in non-pure instructions or
     function returns.
  2. Mark all instructions whose results are in the live set.
  3. Transitively mark operands of live instructions.
  4. Sweep: remove unmarked pure instructions.
"""

from __future__ import annotations
from typing import Dict, List, Set

from lightrail.ir.ssa import Module, Function, BasicBlock, Instruction
from lightrail.ir.ops import Opcode


class DeadCodeEliminationPass:

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            self._dce_function(fn)
        return module

    def _dce_function(self, fn: Function) -> None:
        # Step 1: build def-use info
        # def_map: result_name -> Instruction
        def_map: Dict[str, Instruction] = {}
        for bb in fn.blocks:
            for instr in bb.instructions:
                if instr.result:
                    def_map[instr.result] = instr

        # Step 2: seed live set from non-pure instructions' operands
        live: Set[str] = set()
        worklist: List[str] = []

        for bb in fn.blocks:
            for instr in bb.instructions:
                if not instr.is_pure() or instr.is_terminator():
                    for op in instr.operands:
                        if op not in live:
                            live.add(op)
                            worklist.append(op)
                # Ensure function params are always live
                if instr.op == Opcode.CALL:
                    for op in instr.operands:
                        if op not in live:
                            live.add(op)
                            worklist.append(op)

        # Seed function parameters
        for pname, _ in fn.params:
            if pname not in live:
                live.add(pname)
                worklist.append(pname)

        # Step 3: propagate liveness backwards through def-use edges
        while worklist:
            name = worklist.pop()
            if name not in def_map:
                continue
            instr = def_map[name]
            for op in instr.operands:
                if op not in live:
                    live.add(op)
                    worklist.append(op)

        # Step 4: sweep dead instructions
        for bb in fn.blocks:
            kept: List[Instruction] = []
            for instr in bb.instructions:
                if instr.result and instr.result not in live and instr.is_pure():
                    continue  # dead: drop it
                kept.append(instr)
            bb.instructions = kept

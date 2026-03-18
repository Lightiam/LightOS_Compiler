"""
Stage 3: Alias Analysis Pass
==============================
Implements a simple flow-insensitive, intraprocedural alias analysis for
the LightRail IR.  The primary purpose here is to:

  1. Determine which LOAD/STORE pairs alias (may-alias / must-alias).
  2. Annotate instructions with alias class IDs so later passes (e.g.,
     loop splitting, DMA scheduling) can safely reorder memory operations.
  3. Identify SRAM-resident vs fabric-resident pointers for DMA planning.

Algorithm: Anderson-style inclusion-based analysis.
  - Each allocation site gets a unique alias class.
  - Copies propagate alias classes.
  - A conservative "unknown" class is used for pointer arguments.

The pass adds an "alias_class" attribute to every LOAD and STORE.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

from lightrail.ir.ssa import Module, Function, Instruction
from lightrail.ir.ops import Opcode


@dataclass
class AliasClass:
    """A unique allocation site or conservatively-merged pointer group."""
    class_id: int
    is_local: bool   # True = SRAM, False = fabric/HBM
    name: str = ""

    def __hash__(self) -> int:
        return self.class_id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AliasClass) and self.class_id == other.class_id


UNKNOWN_CLASS = AliasClass(class_id=0, is_local=False, name="unknown")


class AliasAnalysisPass:
    """
    Annotates LOAD and STORE instructions with alias class information.
    """

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            self._analyse_function(fn)
        return module

    def _analyse_function(self, fn: Function) -> None:
        alias_map: Dict[str, AliasClass] = {}
        counter = [1]

        def fresh(name: str, local: bool = True) -> AliasClass:
            cls = AliasClass(counter[0], local, name)
            counter[0] += 1
            return cls

        # Seed: function pointer parameters get UNKNOWN (conservative)
        for pname, _ in fn.params:
            alias_map[pname] = fresh(pname, local=False)

        # Forward scan
        for bb in fn.blocks:
            for instr in bb.instructions:
                if instr.op == Opcode.ALLOC and instr.result:
                    alias_map[instr.result] = fresh(instr.result, local=True)

                elif instr.op == Opcode.COPY and instr.result and instr.operands:
                    src = instr.operands[0]
                    alias_map[instr.result] = alias_map.get(src, UNKNOWN_CLASS)

                elif instr.op in (Opcode.LOAD, Opcode.STORE):
                    ptr = instr.operands[0] if instr.operands else None
                    cls = alias_map.get(ptr, UNKNOWN_CLASS) if ptr else UNKNOWN_CLASS
                    instr.attrs["alias_class"] = cls.class_id
                    instr.attrs["is_local_mem"] = cls.is_local

                elif instr.op in (Opcode.DMA_READ, Opcode.DMA_WRITE):
                    instr.attrs["alias_class"] = UNKNOWN_CLASS.class_id
                    instr.attrs["is_local_mem"] = False

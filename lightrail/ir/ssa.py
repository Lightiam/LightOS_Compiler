"""
LightRail SSA Intermediate Representation
==========================================
Implements an SSA-form IR with:
  - BasicBlocks containing sequences of Instructions
  - Functions containing a CFG of BasicBlocks
  - A Module holding multiple Functions plus metadata
  - A ValueTable mapping SSA names to types
  - A Builder API for constructing IR programmatically

The IR is a high-level, typed, and uniquified SSA form.  After Stage 1
(parsing) operations remain abstract.  Lowering passes progressively
specialise them toward LightRail machine operations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Iterator
import itertools

from lightrail.ir.types import LRType, VOID, FP32
from lightrail.ir.ops import Instruction, Opcode


# ---------------------------------------------------------------------------
# SSA Value table
# ---------------------------------------------------------------------------

class ValueTable:
    """Maps SSA value names (strings) to their types."""

    def __init__(self) -> None:
        self._table: Dict[str, LRType] = {}
        self._counter: Dict[str, int] = {}

    def fresh(self, hint: str = "v", ty: LRType = FP32) -> str:
        """Create a new uniquified SSA name."""
        n = self._counter.get(hint, 0)
        self._counter[hint] = n + 1
        name = f"{hint}{n}"
        self._table[name] = ty
        return name

    def declare(self, name: str, ty: LRType) -> str:
        if name in self._table:
            raise ValueError(f"SSA name '{name}' already defined (SSA violation)")
        self._table[name] = ty
        return name

    def type_of(self, name: str) -> LRType:
        if name not in self._table:
            raise KeyError(f"Unknown SSA value: '{name}'")
        return self._table[name]

    def __contains__(self, name: str) -> bool:
        return name in self._table

    def items(self) -> Iterator[Tuple[str, LRType]]:
        return iter(self._table.items())


# ---------------------------------------------------------------------------
# BasicBlock
# ---------------------------------------------------------------------------

@dataclass
class BasicBlock:
    """A sequence of Instructions ending with exactly one terminator."""
    label: str
    instructions: List[Instruction] = field(default_factory=list)
    predecessors: List[str] = field(default_factory=list)  # block labels
    successors:   List[str] = field(default_factory=list)

    def append(self, instr: Instruction) -> None:
        self.instructions.append(instr)

    def terminator(self) -> Optional[Instruction]:
        if self.instructions and self.instructions[-1].is_terminator():
            return self.instructions[-1]
        return None

    def is_terminated(self) -> bool:
        return self.terminator() is not None

    def __repr__(self) -> str:
        lines = [f"{self.label}:"]
        for instr in self.instructions:
            lines.append(f"  {instr}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Function
# ---------------------------------------------------------------------------

@dataclass
class Function:
    """
    An IR function representing either a host or a device (NCE) kernel.

    Attributes:
        name      : Function name
        params    : [(param_name, type), ...]
        ret_type  : Return type
        blocks    : Ordered list of BasicBlocks (entry is first)
        is_device : True if this kernel runs on the photonic NCE
        values    : SSA value table scoped to this function
        attrs     : Arbitrary metadata (tile_size, wdm_hint, etc.)
    """
    name:       str
    params:     List[Tuple[str, LRType]]
    ret_type:   LRType
    blocks:     List[BasicBlock]    = field(default_factory=list)
    is_device:  bool                = False
    values:     ValueTable          = field(default_factory=ValueTable)
    attrs:      Dict[str, Any]      = field(default_factory=dict)

    def entry_block(self) -> Optional[BasicBlock]:
        return self.blocks[0] if self.blocks else None

    def get_block(self, label: str) -> Optional[BasicBlock]:
        for b in self.blocks:
            if b.label == label:
                return b
        return None

    def add_block(self, label: Optional[str] = None) -> BasicBlock:
        if label is None:
            label = f"bb{len(self.blocks)}"
        bb = BasicBlock(label=label)
        self.blocks.append(bb)
        return bb

    def all_instructions(self) -> Iterator[Instruction]:
        for bb in self.blocks:
            yield from bb.instructions

    def __repr__(self) -> str:
        tag = "device" if self.is_device else "host"
        params_str = ", ".join(f"%{n}: {t}" for n, t in self.params)
        lines = [f"@{tag} fn {self.name}({params_str}) -> {self.ret_type} {{"]
        for bb in self.blocks:
            lines.append(repr(bb))
        lines.append("}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------

@dataclass
class Module:
    """
    Top-level IR container.

    Holds:
      - functions  : all host + device functions
      - globals    : global constant / parameter buffers
      - metadata   : compiler version, source file, target fabric generation
    """
    name:      str
    functions: List[Function]         = field(default_factory=list)
    globals:   Dict[str, Any]         = field(default_factory=dict)
    metadata:  Dict[str, Any]         = field(default_factory=dict)

    def add_function(self, fn: Function) -> Function:
        self.functions.append(fn)
        return fn

    def device_functions(self) -> List[Function]:
        return [f for f in self.functions if f.is_device]

    def host_functions(self) -> List[Function]:
        return [f for f in self.functions if not f.is_device]

    def get_function(self, name: str) -> Optional[Function]:
        for fn in self.functions:
            if fn.name == name:
                return fn
        return None

    def dump(self) -> str:
        lines = [f"module {self.name} {{"]
        for fn in self.functions:
            lines.append(repr(fn))
        lines.append("}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        n_host = len(self.host_functions())
        n_dev  = len(self.device_functions())
        return f"<Module '{self.name}': {n_host} host fn, {n_dev} device fn>"


# ---------------------------------------------------------------------------
# IR Builder
# ---------------------------------------------------------------------------

class Builder:
    """
    Convenience API for building SSA IR programmatically.

    Usage:
        b = Builder(module)
        fn = b.new_function("matmul", params=[("A", ptr_type)], ret=VOID, is_device=True)
        entry = b.new_block(fn)
        b.use_block(entry)
        x = b.emit(Opcode.CONST, ty=INT32, attrs={"value": 42})
    """

    def __init__(self, module: Module) -> None:
        self.module = module
        self._current_fn:    Optional[Function]    = None
        self._current_block: Optional[BasicBlock]  = None
        self._name_gen = itertools.count()

    # -- Functions -----------------------------------------------------------

    def new_function(
        self,
        name: str,
        params: List[Tuple[str, LRType]],
        ret: LRType = VOID,
        is_device: bool = False,
    ) -> Function:
        fn = Function(name=name, params=params, ret_type=ret, is_device=is_device)
        # Pre-register parameters in value table
        for pname, pty in params:
            fn.values.declare(pname, pty)
        self.module.add_function(fn)
        self._current_fn = fn
        return fn

    def use_function(self, fn: Function) -> None:
        self._current_fn = fn

    # -- Blocks --------------------------------------------------------------

    def new_block(self, fn: Optional[Function] = None, label: Optional[str] = None) -> BasicBlock:
        target = fn or self._current_fn
        assert target is not None, "No active function"
        bb = target.add_block(label)
        return bb

    def use_block(self, bb: BasicBlock) -> None:
        self._current_block = bb

    # -- Instruction emission ------------------------------------------------

    def _fresh_name(self, hint: str = "v", ty: LRType = FP32) -> str:
        assert self._current_fn is not None
        return self._current_fn.values.fresh(hint, ty)

    def emit(
        self,
        op: Opcode,
        operands: Optional[List[str]] = None,
        ty: Optional[LRType] = None,
        attrs: Optional[Dict[str, Any]] = None,
        result_hint: str = "v",
    ) -> Optional[str]:
        """
        Emit an instruction into the current block.
        Returns the SSA result name, or None for void-result ops.
        """
        assert self._current_block is not None, "No active block"
        result = None
        if ty is not None and ty != VOID:
            result = self._fresh_name(result_hint, ty)
        instr = Instruction(
            op=op,
            result=result,
            operands=operands or [],
            attrs=attrs or {},
            type_=ty,
        )
        self._current_block.append(instr)
        return result

    # -- Convenience wrappers ------------------------------------------------

    def const(self, value: Any, ty: LRType) -> str:
        return self.emit(Opcode.CONST, ty=ty, attrs={"value": value}, result_hint="c")

    def load(self, ptr: str, ty: LRType) -> str:
        return self.emit(Opcode.LOAD, operands=[ptr], ty=ty, result_hint="ld")

    def store(self, val: str, ptr: str) -> None:
        self.emit(Opcode.STORE, operands=[val, ptr], ty=VOID)

    def fma(self, a: str, b: str, c: str, ty: LRType) -> str:
        return self.emit(Opcode.FMA, operands=[a, b, c], ty=ty, result_hint="fma")

    def ret(self, val: Optional[str] = None) -> None:
        ops = [val] if val else []
        self.emit(Opcode.RET, operands=ops, ty=VOID)

    def br(self, target_label: str) -> None:
        self.emit(Opcode.BR, attrs={"target": target_label}, ty=VOID)

    def cbr(self, cond: str, true_label: str, false_label: str) -> None:
        self.emit(
            Opcode.CBR,
            operands=[cond],
            attrs={"true": true_label, "false": false_label},
            ty=VOID,
        )

    def wdm_bind(self, channel_id: int) -> str:
        from lightrail.ir.types import WavelengthChannelType
        ty = WavelengthChannelType(channel_id)
        return self.emit(
            Opcode.WDM_BIND,
            attrs={"channel": channel_id},
            ty=ty,
            result_hint="wdm",
        )

    def all_reduce(self, val: str, ty: LRType, reduction: str = "sum") -> str:
        return self.emit(
            Opcode.ALL_REDUCE,
            operands=[val],
            ty=ty,
            attrs={"reduction": reduction},
            result_hint="ar",
        )

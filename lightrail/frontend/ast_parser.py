"""
Stage 1: Python AST Parser
===========================
Parses a Python function decorated with @lightrail.jit into the LightRail
high-level SSA IR.  The parser:

  1. Extracts the Python AST from source text or an existing function object.
  2. Classifies each statement as "host" or "device" based on annotations.
  3. Translates device operations into SSA IR instructions, uniquifying all
     variable names per the SSA property.
  4. Returns a Module containing at least one device Function and one host
     entry stub.
"""

from __future__ import annotations
import ast
import inspect
import textwrap
from typing import Any, Callable, Dict, List, Optional, Tuple

from lightrail.ir.types import (
    LRType, infer_from_annotation, python_type_to_lr,
    VOID, INT32, FP32, BOOL, PointerType,
)
from lightrail.ir.ops import Opcode, Instruction
from lightrail.ir.ssa import BasicBlock, Builder, Function, Module, ValueTable


# ---------------------------------------------------------------------------
# Helper: collect function annotations
# ---------------------------------------------------------------------------

def _strip_quotes(s: str) -> str:
    """Strip surrounding quotes from a string-literal annotation."""
    s = s.strip()
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        return s[1:-1]
    return s


def _extract_annotations(fn_def: ast.FunctionDef) -> Dict[str, LRType]:
    """Return {arg_name: LRType} from a function definition's annotations."""
    result: Dict[str, LRType] = {}
    for arg in fn_def.args.args:
        if arg.annotation:
            ann = _strip_quotes(ast.unparse(arg.annotation))
            result[arg.arg] = infer_from_annotation(ann)
        else:
            result[arg.arg] = FP32  # default
    return result


def _annotation_to_type(node: Optional[ast.expr]) -> LRType:
    if node is None:
        return FP32
    return infer_from_annotation(_strip_quotes(ast.unparse(node)))


# ---------------------------------------------------------------------------
# Expression Compiler
# ---------------------------------------------------------------------------

class ExprCompiler(ast.NodeVisitor):
    """
    Translates a Python expression AST sub-tree into a sequence of SSA
    instructions, returning the SSA name of the result.
    """

    def __init__(self, builder: Builder, env: Dict[str, str]) -> None:
        """
        builder : active IR Builder
        env     : maps Python variable names -> SSA value names
        """
        self.builder = builder
        self.env = env

    def compile(self, node: ast.expr) -> str:
        return self.visit(node)

    # -- Literals ------------------------------------------------------------

    def visit_Constant(self, node: ast.Constant) -> str:
        if isinstance(node.value, bool):
            ty = BOOL
        elif isinstance(node.value, int):
            ty = INT32
        else:
            ty = FP32
        return self.builder.const(node.value, ty)

    # -- Names (variable references) ----------------------------------------

    def visit_Name(self, node: ast.Name) -> str:
        name = node.id
        if name in self.env:
            return self.env[name]
        # Treat unknown names as constants (e.g., imported functions)
        return self.builder.const(name, FP32)

    # -- Binary Operations ---------------------------------------------------

    _BINOP_MAP: Dict[type, Tuple[Opcode, Opcode]] = {
        ast.Add:  (Opcode.IADD, Opcode.FADD),
        ast.Sub:  (Opcode.ISUB, Opcode.FSUB),
        ast.Mult: (Opcode.IMUL, Opcode.FMUL),
        ast.Div:  (Opcode.FDIV, Opcode.FDIV),
        ast.FloorDiv: (Opcode.IDIV, Opcode.IDIV),
        ast.Mod:  (Opcode.IMOD, Opcode.IMOD),
        ast.BitAnd: (Opcode.IAND, Opcode.IAND),
        ast.BitOr:  (Opcode.IOR, Opcode.IOR),
        ast.BitXor: (Opcode.IXOR, Opcode.IXOR),
        ast.LShift: (Opcode.ISHL, Opcode.ISHL),
        ast.RShift: (Opcode.ISHR, Opcode.ISHR),
    }

    def visit_BinOp(self, node: ast.BinOp) -> str:
        left  = self.compile(node.left)
        right = self.compile(node.right)
        op_pair = self._BINOP_MAP.get(type(node.op))
        if op_pair is None:
            raise NotImplementedError(f"Unsupported binary op: {type(node.op).__name__}")
        # Naively use FP32 for all results (type inference pass will fix this)
        ty = FP32
        op = op_pair[1]
        return self.builder.emit(op, operands=[left, right], ty=ty, result_hint="tmp")

    # -- Unary Operations ----------------------------------------------------

    def visit_UnaryOp(self, node: ast.UnaryOp) -> str:
        operand = self.compile(node.operand)
        if isinstance(node.op, ast.USub):
            return self.builder.emit(Opcode.FNEG, operands=[operand], ty=FP32, result_hint="neg")
        if isinstance(node.op, ast.Not):
            return self.builder.emit(Opcode.INOT, operands=[operand], ty=BOOL, result_hint="not")
        raise NotImplementedError(f"Unsupported unary op: {type(node.op).__name__}")

    # -- Function Calls ------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> str:
        func_name = ast.unparse(node.func)
        args = [self.compile(a) for a in node.args]

        # Intercept collective primitives
        if "all_reduce" in func_name:
            reduction = "sum"
            if node.keywords:
                for kw in node.keywords:
                    if kw.arg == "reduction":
                        reduction = ast.literal_eval(kw.value)
            return self.builder.emit(
                Opcode.ALL_REDUCE,
                operands=args,
                ty=FP32,
                attrs={"reduction": reduction},
                result_hint="ar",
            )
        if "matmul" in func_name or "mm" in func_name:
            return self.builder.emit(Opcode.MATMUL, operands=args, ty=FP32, result_hint="mm")
        if "dot" in func_name:
            return self.builder.emit(Opcode.DOT, operands=args, ty=FP32, result_hint="dot")

        # Generic call
        return self.builder.emit(
            Opcode.CALL,
            operands=args,
            ty=FP32,
            attrs={"callee": func_name},
            result_hint="call",
        )

    # -- Subscript (array indexing -> load) ----------------------------------

    def visit_Subscript(self, node: ast.Subscript) -> str:
        ptr  = self.compile(node.value)
        idx  = self.compile(node.slice)
        addr = self.builder.emit(Opcode.IADD, operands=[ptr, idx], ty=FP32, result_hint="addr")
        return self.builder.load(addr, FP32)

    # -- Comparison ----------------------------------------------------------

    _CMP_MAP: Dict[type, str] = {
        ast.Eq:  "eq", ast.NotEq: "ne", ast.Lt: "lt",
        ast.LtE: "le", ast.Gt:   "gt", ast.GtE: "ge",
    }

    def visit_Compare(self, node: ast.Compare) -> str:
        left = self.compile(node.left)
        # Only handle first comparator for simplicity
        op   = self._CMP_MAP.get(type(node.ops[0]), "eq")
        right = self.compile(node.comparators[0])
        return self.builder.emit(
            Opcode.FCMP,
            operands=[left, right],
            ty=BOOL,
            attrs={"predicate": op},
            result_hint="cmp",
        )

    def generic_visit(self, node: ast.AST) -> str:  # type: ignore[override]
        raise NotImplementedError(f"ExprCompiler: unsupported node {type(node).__name__}")


# ---------------------------------------------------------------------------
# Statement Compiler
# ---------------------------------------------------------------------------

class StmtCompiler(ast.NodeVisitor):
    """
    Translates a Python function body (list of statements) into SSA.
    Manages the current BasicBlock and SSA environment.
    """

    def __init__(self, builder: Builder, fn: Function) -> None:
        self.builder  = builder
        self.fn       = fn
        self.env: Dict[str, str] = {}   # Python var -> SSA name
        self.expr     = ExprCompiler(builder, self.env)
        # Seed env with function parameters
        for pname, _ in fn.params:
            self.env[pname] = pname

    def compile_body(self, stmts: List[ast.stmt]) -> None:
        for stmt in stmts:
            self.visit(stmt)

    # -- Assignments ---------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        val_name = self.expr.compile(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.env[target.id] = val_name
            elif isinstance(target, ast.Subscript):
                # a[i] = v  => STORE
                ptr = self.expr.compile(target.value)
                idx = self.expr.compile(target.slice)
                addr = self.builder.emit(
                    Opcode.IADD, operands=[ptr, idx], ty=FP32, result_hint="addr"
                )
                self.builder.store(val_name, addr)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        # x: float32 = expr
        ty = _annotation_to_type(node.annotation)
        if node.value:
            raw = self.expr.compile(node.value)
            # Emit a cast to the declared type if needed
            cast = self.builder.emit(
                Opcode.CAST, operands=[raw], ty=ty, attrs={"to": repr(ty)}, result_hint="cast"
            )
            if isinstance(node.target, ast.Name):
                self.env[node.target.id] = cast

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # x += y  => x = x + y
        binop = ast.BinOp(left=node.target, op=node.op, right=node.value)
        ast.copy_location(binop, node)
        assign = ast.Assign(
            targets=[node.target],
            value=binop,
            lineno=node.lineno,
            col_offset=node.col_offset,
        )
        self.visit_Assign(assign)

    # -- Return --------------------------------------------------------------

    def visit_Return(self, node: ast.Return) -> None:
        if node.value:
            val = self.expr.compile(node.value)
            self.builder.ret(val)
        else:
            self.builder.ret()

    # -- For loops -----------------------------------------------------------

    def visit_For(self, node: ast.For) -> None:
        # Translate `for i in range(n)` into loop IR
        # Emit loop markers; full canonicalisation happens in pass 3
        cond_bb  = self.builder.new_block(label=f"loop_cond_{id(node)}")
        body_bb  = self.builder.new_block(label=f"loop_body_{id(node)}")
        exit_bb  = self.builder.new_block(label=f"loop_exit_{id(node)}")

        self.builder.br(cond_bb.label)
        self.builder.use_block(cond_bb)
        self.builder.emit(Opcode.LOOP_BEGIN, ty=VOID, attrs={"ast_node": id(node)})

        # Compile range argument as trip count
        if (isinstance(node.iter, ast.Call) and
                isinstance(node.iter.func, ast.Name) and
                node.iter.func.id == "range"):
            args = node.iter.args
            if len(args) == 1:
                end_val  = self.expr.compile(args[0])
                start    = self.builder.const(0, INT32)
                step     = self.builder.const(1, INT32)
            elif len(args) == 2:
                start    = self.expr.compile(args[0])
                end_val  = self.expr.compile(args[1])
                step     = self.builder.const(1, INT32)
            else:
                start    = self.expr.compile(args[0])
                end_val  = self.expr.compile(args[1])
                step     = self.expr.compile(args[2])
        else:
            start = self.builder.const(0, INT32)
            end_val = self.builder.const(1, INT32)
            step    = self.builder.const(1, INT32)

        # Phi for loop induction variable
        iv_name = self.fn.values.fresh("iv", INT32)
        self.fn.values.declare.__func__  # just check it's there
        phi = Instruction(
            op=Opcode.PHI,
            result=iv_name,
            operands=[start, f"iv_next_{id(node)}"],
            attrs={"blocks": [self.builder._current_block.label, body_bb.label]},
            type_=INT32,
        )
        cond_bb.append(phi)

        if isinstance(node.target, ast.Name):
            self.env[node.target.id] = iv_name

        cmp = self.builder.emit(
            Opcode.ICMP,
            operands=[iv_name, end_val],
            ty=BOOL,
            attrs={"predicate": "lt"},
            result_hint="loop_cond",
        )
        self.builder.cbr(cmp, body_bb.label, exit_bb.label)

        # Body
        self.builder.use_block(body_bb)
        self.compile_body(node.body)

        # Increment
        iv_next = self.builder.emit(
            Opcode.IADD,
            operands=[iv_name, step],
            ty=INT32,
            result_hint=f"iv_next_{id(node)}",
        )
        # Update env
        if isinstance(node.target, ast.Name):
            self.env[node.target.id] = iv_next

        self.builder.emit(Opcode.LOOP_END, ty=VOID)
        self.builder.br(cond_bb.label)

        self.builder.use_block(exit_bb)

    # -- If statements -------------------------------------------------------

    def visit_If(self, node: ast.If) -> None:
        then_bb = self.builder.new_block(label=f"if_then_{id(node)}")
        else_bb = self.builder.new_block(label=f"if_else_{id(node)}")
        cont_bb = self.builder.new_block(label=f"if_cont_{id(node)}")

        cond = self.expr.compile(node.test)
        self.builder.cbr(cond, then_bb.label, else_bb.label)

        self.builder.use_block(then_bb)
        self.compile_body(node.body)
        if not self.builder._current_block.is_terminated():
            self.builder.br(cont_bb.label)

        self.builder.use_block(else_bb)
        if node.orelse:
            self.compile_body(node.orelse)
        if not self.builder._current_block.is_terminated():
            self.builder.br(cont_bb.label)

        self.builder.use_block(cont_bb)

    # -- Expression statements -----------------------------------------------

    def visit_Expr(self, node: ast.Expr) -> None:
        self.expr.compile(node.value)

    def generic_visit(self, node: ast.AST) -> None:
        pass  # silently skip unsupported statements in this pass


# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------

class ASTParser:
    """
    Converts a Python callable decorated with @lightrail.jit into a Module.
    """

    def parse_function(
        self,
        fn: Callable,
        device: bool = True,
    ) -> Module:
        """Parse a Python function into a LightRail IR Module."""
        src = textwrap.dedent(inspect.getsource(fn))
        tree = ast.parse(src)
        fn_def = self._find_fn_def(tree, fn.__name__)
        return self._compile_fn_def(fn_def, module_name=fn.__name__, device=device)

    def parse_source(
        self,
        source: str,
        fn_name: str,
        device: bool = True,
    ) -> Module:
        """Parse Python source text into a LightRail IR Module."""
        tree = ast.parse(textwrap.dedent(source))
        fn_def = self._find_fn_def(tree, fn_name)
        return self._compile_fn_def(fn_def, module_name=fn_name, device=device)

    # -- Internals -----------------------------------------------------------

    @staticmethod
    def _find_fn_def(tree: ast.Module, name: str) -> ast.FunctionDef:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        raise ValueError(f"Function '{name}' not found in source")

    def _compile_fn_def(
        self,
        fn_def: ast.FunctionDef,
        module_name: str,
        device: bool,
    ) -> Module:
        annotations = _extract_annotations(fn_def)
        ret_ty = _annotation_to_type(fn_def.returns)
        params: List[Tuple[str, LRType]] = [
            (arg.arg, annotations.get(arg.arg, FP32))
            for arg in fn_def.args.args
        ]

        module  = Module(name=module_name, metadata={"source_fn": fn_def.name})
        builder = Builder(module)
        fn      = builder.new_function(fn_def.name, params=params, ret=ret_ty, is_device=device)
        entry   = builder.new_block(fn, label="entry")
        builder.use_block(entry)

        stmt_compiler = StmtCompiler(builder, fn)
        stmt_compiler.compile_body(fn_def.body)

        # Ensure entry block is terminated
        if not entry.is_terminated():
            if not any(bb.is_terminated() for bb in fn.blocks):
                builder.use_block(fn.blocks[-1])
                builder.ret()

        return module

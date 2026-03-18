"""
Framework Adapter Base
=======================
Abstract base class for all AI framework adapters.

The strategy document states:
    "Your framework adapters are super important, super valuable.
     The AI frameworks could be connected, Fabric OS with the Photonic
     Compiler would be able to execute that workload partitioning."

Every adapter must:
  1. Accept a framework-native model/function object.
  2. Extract its computation graph (nodes + edges).
  3. Translate it into a LightRail IR Module.
  4. Annotate the Module with workload-partitioning metadata needed by
     the TopologyAwareRouter.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lightrail.ir.ssa import Module, Function, Builder
from lightrail.ir.types import FP32, VOID


@dataclass
class AdapterGraphNode:
    """A single operator node extracted from a framework graph."""
    node_id:    str
    op_name:    str                    # e.g. "aten::mm", "jax.lax.dot"
    inputs:     List[str]              # input node_ids
    outputs:    List[str]              # output node_ids
    attrs:      Dict[str, Any] = field(default_factory=dict)
    shape:      Optional[Tuple[int, ...]] = None
    dtype:      str = "float32"


@dataclass
class AdapterGraph:
    """Framework-agnostic computation graph extracted by an adapter."""
    framework:  str
    nodes:      List[AdapterGraphNode] = field(default_factory=list)
    inputs:     List[str]              = field(default_factory=list)
    outputs:    List[str]              = field(default_factory=list)
    metadata:   Dict[str, Any]         = field(default_factory=dict)

    def topological_order(self) -> List[AdapterGraphNode]:
        """Return nodes in dependency order (inputs before outputs)."""
        id_to_node = {n.node_id: n for n in self.nodes}
        visited: set  = set()
        order:   List[AdapterGraphNode] = []

        def visit(nid: str) -> None:
            if nid in visited or nid not in id_to_node:
                return
            visited.add(nid)
            node = id_to_node[nid]
            for inp in node.inputs:
                visit(inp)
            order.append(node)

        for node in self.nodes:
            visit(node.node_id)

        return order


class FrameworkAdapter(ABC):
    """
    Abstract base for AI framework adapters.

    Concrete subclasses: PyTorchAdapter, JAXAdapter.
    """

    @property
    @abstractmethod
    def framework_name(self) -> str:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """True if the framework is installed and importable."""
        ...

    @abstractmethod
    def extract_graph(self, model_or_fn: Any, example_inputs: Optional[List[Any]] = None) -> AdapterGraph:
        """Extract a framework-agnostic AdapterGraph from the model."""
        ...

    def to_module(self, graph: AdapterGraph, module_name: str = "") -> Module:
        """
        Translate an AdapterGraph into a LightRail IR Module.
        Common implementation shared by all subclasses.
        """
        from lightrail.ir.ops import Opcode
        from lightrail.ir.types import infer_from_annotation

        name   = module_name or graph.metadata.get("name", "unnamed")
        module = Module(
            name=name,
            metadata={
                "source_framework": graph.framework,
                "adapter_version":  "0.1",
                **graph.metadata,
            },
        )
        builder = Builder(module)

        # Build one device function per graph
        params  = [(f"arg{i}", FP32) for i in range(len(graph.inputs))]
        fn      = builder.new_function(name, params=params, ret=VOID, is_device=True)
        entry   = builder.new_block(fn, "entry")
        builder.use_block(entry)

        env: Dict[str, str] = {}
        for i, inp_id in enumerate(graph.inputs):
            env[inp_id] = f"arg{i}"

        for node in graph.topological_order():
            op = self._map_op(node.op_name)
            operands = [env.get(inp, inp) for inp in node.inputs if inp in env]

            ty = infer_from_annotation(node.dtype)

            result = builder.emit(
                op,
                operands=operands,
                ty=ty,
                attrs={
                    "framework_op": node.op_name,
                    "shape":        str(node.shape),
                    **node.attrs,
                },
                result_hint=f"op_{node.node_id}",
            )
            if result:
                for out_id in node.outputs:
                    env[out_id] = result

        builder.ret()

        # Annotate for workload partitioning
        fn.attrs["workload_partitioning"] = True
        fn.attrs["source_nodes"]          = len(graph.nodes)
        fn.attrs["framework"]             = graph.framework

        return module

    @staticmethod
    def _map_op(framework_op: str) -> "Opcode":
        """Map a framework operator name to a LightRail Opcode."""
        from lightrail.ir.ops import Opcode

        name = framework_op.lower()
        if any(k in name for k in ("mm", "matmul", "gemm", "dot_general")):
            return Opcode.MATMUL
        if any(k in name for k in ("add", "plus")):
            return Opcode.FADD
        if any(k in name for k in ("mul", "times")):
            return Opcode.FMUL
        if any(k in name for k in ("relu", "gelu", "silu", "activation")):
            return Opcode.FMUL   # approximate with scale op
        if any(k in name for k in ("reduce", "sum", "mean")):
            return Opcode.ALL_REDUCE
        if any(k in name for k in ("conv",)):
            return Opcode.MATMUL   # convolution as tiled matmul
        if any(k in name for k in ("softmax",)):
            return Opcode.FADD
        if any(k in name for k in ("norm", "layer_norm", "batch_norm")):
            return Opcode.FMA
        return Opcode.CALL

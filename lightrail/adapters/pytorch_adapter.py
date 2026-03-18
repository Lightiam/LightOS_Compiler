"""
PyTorch Framework Adapter
==========================
Ingests a PyTorch `nn.Module` or `torch.fx`-traced graph and converts it
to a LightRail IR Module for compilation by the photonic compiler.

Extraction pipeline:
  1. If `torch.fx` is available, trace the model symbolically using
     `torch.fx.symbolic_trace` to get a clean computation graph.
  2. Walk the FX graph nodes and map each to an AdapterGraphNode.
  3. Call `FrameworkAdapter.to_module()` to build the LightRail IR.

Falls back gracefully if PyTorch is not installed:  `is_available()` returns
False and no import errors are raised, allowing the compiler to be used
without a PyTorch installation.

This adapter is what the strategy document describes as:
    "The AI frameworks could be connected, Fabric OS with the Photonic
     Compiler would be able to execute that workload partitioning."
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from lightrail.adapters.base import FrameworkAdapter, AdapterGraph, AdapterGraphNode
from lightrail.ir.ssa import Module


class PyTorchAdapter(FrameworkAdapter):
    """
    Adapter for PyTorch `nn.Module` and `torch.fx` traced graphs.

    Usage:
        adapter = PyTorchAdapter()
        if adapter.is_available():
            graph  = adapter.extract_graph(my_model, example_inputs=[x])
            module = adapter.to_module(graph, "my_model")
            # → pass module into CompilationPipeline
    """

    @property
    def framework_name(self) -> str:
        return "pytorch"

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    def extract_graph(
        self,
        model_or_fn: Any,
        example_inputs: Optional[List[Any]] = None,
    ) -> AdapterGraph:
        """
        Extract an AdapterGraph from a PyTorch model.

        Uses torch.fx for symbolic tracing when available; falls back to
        operator-level introspection via __class__.__name__ walking.
        """
        if not self.is_available():
            raise RuntimeError("PyTorch is not installed. Install with: pip install torch")

        try:
            return self._trace_fx(model_or_fn, example_inputs)
        except Exception:
            return self._introspect_module(model_or_fn)

    # -- FX tracing ----------------------------------------------------------

    def _trace_fx(
        self, model: Any, example_inputs: Optional[List[Any]]
    ) -> AdapterGraph:
        import torch
        import torch.fx as fx

        traced = fx.symbolic_trace(model)
        graph  = AdapterGraph(
            framework="pytorch",
            metadata={
                "name":      getattr(model, "__class__", type(model)).__name__,
                "traced_by": "torch.fx",
            },
        )

        node_map: Dict[str, str] = {}   # fx node name -> adapter node id

        for node in traced.graph.nodes:
            node_id = node.name
            node_map[node.name] = node_id

            if node.op == "placeholder":
                graph.inputs.append(node_id)
                adapter_node = AdapterGraphNode(
                    node_id=node_id,
                    op_name="input",
                    inputs=[],
                    outputs=[node_id],
                    dtype="float32",
                )

            elif node.op == "output":
                inputs = [node_map.get(a.name, a.name)
                          for a in node.args[0] if hasattr(a, "name")]
                graph.outputs.extend(inputs)
                continue

            elif node.op == "call_function":
                op_name = getattr(node.target, "__name__", str(node.target))
                inputs  = [node_map.get(a.name, a.name)
                           for a in node.args if hasattr(a, "name")]
                shape   = self._infer_shape(node)
                adapter_node = AdapterGraphNode(
                    node_id=node_id,
                    op_name=f"aten::{op_name}",
                    inputs=inputs,
                    outputs=[node_id],
                    shape=shape,
                    dtype="float32",
                )

            elif node.op == "call_module":
                submod = traced.get_submodule(node.target)
                op_name = submod.__class__.__name__
                inputs  = [node_map.get(a.name, a.name)
                           for a in node.args if hasattr(a, "name")]
                shape   = self._infer_shape(node)
                attrs   = {}
                # Extract layer parameters as hints
                if hasattr(submod, "weight"):
                    w = submod.weight
                    attrs["weight_shape"] = str(tuple(w.shape))
                if hasattr(submod, "bias") and submod.bias is not None:
                    attrs["has_bias"] = True
                adapter_node = AdapterGraphNode(
                    node_id=node_id,
                    op_name=f"nn::{op_name}",
                    inputs=inputs,
                    outputs=[node_id],
                    shape=shape,
                    attrs=attrs,
                    dtype="float32",
                )

            elif node.op == "call_method":
                op_name = node.target
                inputs  = [node_map.get(a.name, a.name)
                           for a in node.args if hasattr(a, "name")]
                adapter_node = AdapterGraphNode(
                    node_id=node_id,
                    op_name=f"method::{op_name}",
                    inputs=inputs,
                    outputs=[node_id],
                )

            elif node.op == "get_attr":
                adapter_node = AdapterGraphNode(
                    node_id=node_id,
                    op_name="get_attr",
                    inputs=[],
                    outputs=[node_id],
                    attrs={"target": node.target},
                )
            else:
                continue

            graph.nodes.append(adapter_node)

        return graph

    # -- Fallback introspection ---------------------------------------------

    def _introspect_module(self, model: Any) -> AdapterGraph:
        """Simple introspection when FX tracing fails (e.g., dynamic models)."""
        graph = AdapterGraph(
            framework="pytorch",
            metadata={
                "name":      getattr(model, "__class__", type(model)).__name__,
                "traced_by": "introspection",
            },
        )

        try:
            import torch.nn as nn
            prev_id = "input_0"
            graph.inputs.append(prev_id)
            graph.nodes.append(AdapterGraphNode(
                node_id=prev_id, op_name="input",
                inputs=[], outputs=[prev_id],
            ))

            for i, (name, layer) in enumerate(model.named_modules()):
                if name == "":
                    continue
                node_id  = f"layer_{i}"
                op_name  = f"nn::{layer.__class__.__name__}"
                attrs    = {}
                if hasattr(layer, "weight") and layer.weight is not None:
                    attrs["weight_shape"] = str(tuple(layer.weight.shape))
                node = AdapterGraphNode(
                    node_id=node_id,
                    op_name=op_name,
                    inputs=[prev_id],
                    outputs=[node_id],
                    attrs=attrs,
                )
                graph.nodes.append(node)
                prev_id = node_id

            graph.outputs.append(prev_id)
        except Exception:
            pass

        return graph

    @staticmethod
    def _infer_shape(node: Any) -> Optional[Tuple[int, ...]]:
        try:
            meta = node.meta.get("tensor_meta")
            if meta and hasattr(meta, "shape"):
                return tuple(meta.shape)
        except Exception:
            pass
        return None

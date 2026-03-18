"""
JAX Framework Adapter
======================
Ingests a JAX function (decorated with `@jax.jit` or plain Python) and
converts it to a LightRail IR Module using JAX's tracing machinery.

Extraction pipeline:
  1. Use `jax.make_jaxpr` to capture the JAX expression (JAXPR) —
     JAX's own SSA-like IR.
  2. Walk the JAXPR equations and map each primitive to an AdapterGraphNode.
  3. Call `FrameworkAdapter.to_module()` to build the LightRail IR.

Falls back gracefully if JAX is not installed.

JAX's functional, pure-function model maps cleanly onto LightRail's SSA IR,
making this the most direct framework integration.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from lightrail.adapters.base import FrameworkAdapter, AdapterGraph, AdapterGraphNode
from lightrail.ir.ssa import Module


class JAXAdapter(FrameworkAdapter):
    """
    Adapter for JAX functions and `flax.nn.Module`-like objects.

    Usage:
        adapter = JAXAdapter()
        if adapter.is_available():
            import jax.numpy as jnp
            graph  = adapter.extract_graph(my_fn, example_inputs=[jnp.ones((64,64))])
            module = adapter.to_module(graph, "my_fn")
    """

    @property
    def framework_name(self) -> str:
        return "jax"

    def is_available(self) -> bool:
        try:
            import jax  # noqa: F401
            return True
        except ImportError:
            return False

    def extract_graph(
        self,
        model_or_fn: Any,
        example_inputs: Optional[List[Any]] = None,
    ) -> AdapterGraph:
        if not self.is_available():
            raise RuntimeError("JAX is not installed. Install with: pip install jax")

        try:
            return self._trace_jaxpr(model_or_fn, example_inputs or [])
        except Exception:
            return self._fallback_graph(model_or_fn)

    # -- JAXPR tracing -------------------------------------------------------

    def _trace_jaxpr(self, fn: Any, example_inputs: List[Any]) -> AdapterGraph:
        import jax
        import jax.numpy as jnp

        # Create abstract values for tracing if no inputs provided
        if not example_inputs:
            example_inputs = [jnp.ones((64,))]

        jaxpr = jax.make_jaxpr(fn)(*example_inputs)

        graph = AdapterGraph(
            framework="jax",
            metadata={
                "name":       getattr(fn, "__name__", "jax_fn"),
                "traced_by":  "jax.make_jaxpr",
                "jaxpr_str":  str(jaxpr)[:256],
            },
        )

        # Input variables
        for i, var in enumerate(jaxpr.jaxpr.invars):
            node_id = f"invar_{i}"
            graph.inputs.append(node_id)
            graph.nodes.append(AdapterGraphNode(
                node_id=node_id,
                op_name="input",
                inputs=[],
                outputs=[node_id],
                shape=tuple(var.aval.shape) if hasattr(var.aval, "shape") else None,
                dtype=str(var.aval.dtype) if hasattr(var.aval, "dtype") else "float32",
            ))

        var_map: Dict[Any, str] = {
            var: f"invar_{i}" for i, var in enumerate(jaxpr.jaxpr.invars)
        }

        # Equations (operations)
        for eq_idx, eqn in enumerate(jaxpr.jaxpr.eqns):
            prim_name = eqn.primitive.name
            node_id   = f"eqn_{eq_idx}_{prim_name}"

            inputs = [var_map.get(v, f"const_{id(v)}") for v in eqn.invars]
            outputs = []
            for out_var in eqn.outvars:
                out_id = f"out_{eq_idx}_{id(out_var)}"
                var_map[out_var] = out_id
                outputs.append(out_id)

            shape = None
            dtype = "float32"
            if eqn.outvars:
                try:
                    aval = eqn.outvars[0].aval
                    shape = tuple(aval.shape) if hasattr(aval, "shape") else None
                    dtype = str(aval.dtype)   if hasattr(aval, "dtype") else "float32"
                except Exception:
                    pass

            # Map JAX primitive to friendlier name for the base op mapper
            friendly = self._jax_to_friendly(prim_name, eqn.params)

            graph.nodes.append(AdapterGraphNode(
                node_id=node_id,
                op_name=f"jax.lax.{friendly}",
                inputs=inputs,
                outputs=outputs,
                shape=shape,
                dtype=dtype,
                attrs={"jax_params": {k: str(v) for k, v in eqn.params.items()}},
            ))

        # Output variables
        for var in jaxpr.jaxpr.outvars:
            oid = var_map.get(var)
            if oid:
                graph.outputs.append(oid)

        return graph

    # -- Fallback ------------------------------------------------------------

    def _fallback_graph(self, fn: Any) -> AdapterGraph:
        graph = AdapterGraph(
            framework="jax",
            metadata={"name": getattr(fn, "__name__", "jax_fn"), "traced_by": "fallback"},
        )
        # Minimal graph: single input → single "call" → output
        graph.inputs.append("input_0")
        graph.nodes.append(AdapterGraphNode(
            node_id="input_0", op_name="input", inputs=[], outputs=["input_0"],
        ))
        graph.nodes.append(AdapterGraphNode(
            node_id="call_0",
            op_name=f"jax::{getattr(fn, '__name__', 'fn')}",
            inputs=["input_0"],
            outputs=["output_0"],
        ))
        graph.outputs.append("output_0")
        return graph

    @staticmethod
    def _jax_to_friendly(prim_name: str, params: Dict[str, Any]) -> str:
        """Map a JAX primitive name to a friendly op name for the base mapper."""
        mapping = {
            "dot_general":   "matmul",
            "conv_general_dilated": "conv",
            "add":           "add",
            "mul":           "mul",
            "reduce_sum":    "reduce_sum",
            "broadcast_in_dim": "broadcast",
            "reshape":       "reshape",
            "transpose":     "transpose",
            "exp":           "exp",
            "log":           "log",
            "max":           "reduce_max",
            "psum":          "all_reduce",
        }
        return mapping.get(prim_name, prim_name)

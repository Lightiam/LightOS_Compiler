"""
LightRail Framework Adapters
=============================
Connect standard AI frameworks (PyTorch, JAX) to the LightRail photonic
compiler, enabling workload partitioning and topology-aware compilation
without requiring code changes in the AI framework itself.
"""
from lightrail.adapters.base import (
    FrameworkAdapter, AdapterGraph, AdapterGraphNode,
)
from lightrail.adapters.pytorch_adapter import PyTorchAdapter
from lightrail.adapters.jax_adapter     import JAXAdapter


def get_adapter(framework: str) -> FrameworkAdapter:
    """
    Return the appropriate adapter for the named framework.

    Args:
        framework: "pytorch", "torch", "jax", or "auto"

    For "auto", returns the first available adapter.
    """
    framework = framework.lower().strip()

    if framework in ("pytorch", "torch"):
        return PyTorchAdapter()
    if framework == "jax":
        return JAXAdapter()
    if framework == "auto":
        for adapter_cls in (PyTorchAdapter, JAXAdapter):
            a = adapter_cls()
            if a.is_available():
                return a
        raise RuntimeError("No AI framework found. Install PyTorch or JAX.")

    raise ValueError(f"Unknown framework: '{framework}'. Use 'pytorch', 'jax', or 'auto'.")


__all__ = [
    "FrameworkAdapter", "AdapterGraph", "AdapterGraphNode",
    "PyTorchAdapter", "JAXAdapter", "get_adapter",
]

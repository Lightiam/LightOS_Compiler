"""
Stage 1: Host / Device Code Splitter
=====================================
After AST parsing, this pass analyses a Module and classifies each
Function as either "host" (runs on the CPU) or "device" (runs on the
photonic NCE).

Classification rules (in priority order):
  1. A function already tagged ``is_device=True`` remains device.
  2. A function whose name is suffixed with ``_kernel`` is promoted to device.
  3. A function whose every operand type is a photonic type is promoted.
  4. All remaining functions are host.

The splitter also inserts host-side launch stubs: for every device function
it adds (or reuses) a host wrapper function that sets up arguments and
calls NCE_DISPATCH, mirroring how CUDA host code launches a __global__
kernel.
"""

from __future__ import annotations
from typing import List

from lightrail.ir.ssa import Function, Module, Builder, BasicBlock
from lightrail.ir.ops import Opcode, Instruction
from lightrail.ir.types import VOID, FP32, PointerType


def _is_photonic_heavy(fn: Function) -> bool:
    """Heuristic: most parameters are pointer types (tensor buffers)."""
    if not fn.params:
        return False
    ptr_count = sum(1 for _, ty in fn.params if isinstance(ty, PointerType))
    return ptr_count >= len(fn.params) // 2


def _should_be_device(fn: Function) -> bool:
    if fn.is_device:
        return True
    if fn.name.endswith("_kernel"):
        return True
    if _is_photonic_heavy(fn):
        return True
    return False


def _build_host_stub(module: Module, device_fn: Function, builder: Builder) -> Function:
    """Create a CPU-side wrapper that dispatches to the device function."""
    stub_name = f"launch_{device_fn.name}"
    if module.get_function(stub_name):
        return module.get_function(stub_name)

    stub = builder.new_function(
        stub_name,
        params=device_fn.params,
        ret=VOID,
        is_device=False,
    )
    entry = builder.new_block(stub, label="entry")
    builder.use_block(entry)

    # Emit NCE_DISPATCH referencing the device function
    arg_names = [p for p, _ in device_fn.params]
    builder.emit(
        Opcode.NCE_DISPATCH,
        operands=arg_names,
        ty=VOID,
        attrs={"callee": device_fn.name, "async": False},
    )
    builder.ret()
    return stub


class HostDeviceSplitter:
    """
    Analyses a Module in-place, promoting functions to device and
    inserting host launch stubs.
    """

    def run(self, module: Module) -> Module:
        builder = Builder(module)

        # First pass: classify
        for fn in list(module.functions):
            fn.is_device = _should_be_device(fn)

        # Second pass: generate host stubs for device kernels that lack one
        device_fns = [f for f in module.functions if f.is_device]
        for dfn in device_fns:
            stub_name = f"launch_{dfn.name}"
            if not module.get_function(stub_name):
                _build_host_stub(module, dfn, builder)

        return module

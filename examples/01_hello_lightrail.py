"""
Example 01: Hello LightRail
============================
The simplest possible @lightrail.jit decorated kernel.
Demonstrates decorator usage, IR introspection, and JIT dispatch.
"""

import lightrail


# ---------------------------------------------------------------------------
# Step 1: Decorate a Python function as a LightRail kernel
# ---------------------------------------------------------------------------

@lightrail.jit
def vector_add(a: "float32", b: "float32") -> "float32":
    """Add two floating-point scalars on the photonic NCE."""
    return a + b


# ---------------------------------------------------------------------------
# Step 2: Inspect the compiled IR
# ---------------------------------------------------------------------------

print("=" * 60)
print("LightRail IR dump:")
print("=" * 60)
print(vector_add.ir())

# ---------------------------------------------------------------------------
# Step 3: Dispatch to the Fabric OS (simulated)
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("Dispatching kernel to Fabric OS (simulation):")
print("=" * 60)

descriptor = vector_add(1.0, 2.0)
print(f"Kernel state:       {descriptor.state.name}")
print(f"Dispatch latency:   {descriptor.latency_ns():.1f} ns")

# ---------------------------------------------------------------------------
# Step 4: Inspect compilation details
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("Compilation summary:")
print("=" * 60)

result = lightrail.CompilationPipeline().compile_function(vector_add.__wrapped__)
print(result.summary())

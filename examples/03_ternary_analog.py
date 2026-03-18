"""
Example 03: Ternary & Analog Compute
======================================
Demonstrates LightRail's photonic-native compute modes:

  - Ternary Logic (Layers 1–5): {-1, 0, +1} mapped to optical power levels.
    ~100× more energy-efficient than FP32 for weight-heavy inference.

  - Analog Wave Compute (Layers 6–7): continuous-amplitude MZI arrays.
    Enables O(1) matrix-vector products via optical interference.

This example compiles a ternary neural network inference kernel and
shows how the compiler maps weights to optical power levels.
"""

import lightrail
from lightrail.codegen.ternary import (
    quantise_to_ternary, pack_ternary_word, unpack_ternary_word,
    ternary_dot, mzi_phase_for_weight, TernaryEncodingPass,
)
from lightrail.ir.ssa import Module, Builder
from lightrail.ir.ops import Opcode
from lightrail.ir.types import FP32
from lightrail.pipeline import CompilationPipeline


# ---------------------------------------------------------------------------
# Part 1: Ternary weight quantisation
# ---------------------------------------------------------------------------

print("=" * 60)
print("Part 1: Ternary Weight Quantisation")
print("=" * 60)

# Simulate FP32 weights from a small neural network layer
weights_fp32 = [-0.9, 0.1, 0.7, -0.3, 0.85, 0.0, -0.6, 0.4]

ternary_weights = quantise_to_ternary(weights_fp32, threshold=0.5)
print(f"FP32 weights:    {[f'{w:+.2f}' for w in weights_fp32]}")
print(f"Ternary weights: {ternary_weights}")

# Pack into 64-bit optical word (2 bits per symbol, 32 symbols max)
packed = pack_ternary_word(ternary_weights)
print(f"Packed word:     0x{packed:016x}")

# Round-trip check
unpacked = unpack_ternary_word(packed, len(ternary_weights))
print(f"Unpacked:        {unpacked}")
assert unpacked == ternary_weights, "Pack/unpack round-trip failed!"
print("Round-trip: OK")

# Ternary dot product (what the NCE computes natively)
activations = [1, 0, 1, -1, 1, 0, -1, 1]
dot = ternary_dot(ternary_weights, activations)
print(f"\nActivations:     {activations}")
print(f"Ternary dot:     {dot}  (native optical accumulation)")

# ---------------------------------------------------------------------------
# Part 2: MZI phase calculation for analog weights
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("Part 2: MZI Phase Mapping (Analog Layer 6–7)")
print("=" * 60)

import math

analog_weights = [0.0, 0.25, 0.5, 0.75, 1.0]
print(f"{'Weight':>10} {'MZI Phase (rad)':>18} {'Transmission':>14}")
print("-" * 45)
for w in analog_weights:
    phase = mzi_phase_for_weight(w)
    # Verify: cos^2(phase/2) should equal w
    transmission = math.cos(phase / 2) ** 2
    print(f"{w:>10.2f} {phase:>18.4f} {transmission:>14.4f}")

# ---------------------------------------------------------------------------
# Part 3: Compile a ternary inference kernel
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("Part 3: Ternary Kernel IR Compilation")
print("=" * 60)

# Build IR manually for a ternary dot product
m = Module(name="ternary_inference")
b = Builder(m)

fn = b.new_function(
    "ternary_dot_kernel",
    params=[("weights", FP32), ("activations", FP32)],
    ret=FP32,
    is_device=True,
)
entry = b.new_block(fn, "entry")
b.use_block(entry)

# Emit native ternary dot product
result = b.emit(
    Opcode.TDOT,
    operands=["weights", "activations"],
    ty=FP32,
    result_hint="out",
)
b.ret(result)

# Run ternary encoding pass
TernaryEncodingPass().run(m)

# Show IR with ternary encode/decode wrappers
print("\nCompiled IR with photonic ternary ops:")
print(m.dump())

# Run full pipeline
pipeline = CompilationPipeline()
cr = pipeline.compile_module(m)

print("\n" + "=" * 60)
print("Full pipeline result:")
print("=" * 60)
print(cr.summary())

ops_in_output = [i.op for i in cr.module.get_function("ternary_dot_kernel").all_instructions()]
print(f"\nOps in output IR: {[op.name for op in set(ops_in_output)]}")

assert Opcode.TERNARY_ENCODE in ops_in_output, "TERNARY_ENCODE not found!"
assert Opcode.TERNARY_DECODE in ops_in_output, "TERNARY_DECODE not found!"
print("\nTernary native encode/decode: VERIFIED")
print("(Mapped to Layers 1-5 of the 20-layer photonic fabric)")

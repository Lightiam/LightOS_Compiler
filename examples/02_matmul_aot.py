"""
Example 02: Matrix Multiplication — AOT Compilation
=====================================================
Demonstrates ahead-of-time (AOT) compilation of a matrix multiply kernel.
The compiled binary is serialised to a .lrnpu file that the Fabric OS can
load without any JIT overhead at runtime.

Also showcases:
  - Tiled software pipelining via the Python API
  - WDM channel assignment (no warp scheduling)
  - Fat binary bundling for multi-generation support
"""

import lightrail
from lightrail.pipeline import CompilationPipeline, CompileOptions
from lightrail.codegen.fat_binary import FatBinaryBundler


# ---------------------------------------------------------------------------
# Kernel definition
# ---------------------------------------------------------------------------

@lightrail.jit(mode="aot", num_wdm_channels=64)
def matmul_kernel(
    A: "float32",
    B: "float32",
    C: "float32",
    M: "int32",
    N: "int32",
    K: "int32",
) -> "void":
    """
    Tiled matrix multiply: C = A @ B
    The compiler will:
      1. Split the K-loop into TILE_LOAD / TILE_COMPUTE / TILE_STORE stages
      2. Assign independent tile computations to separate WDM channels
      3. Route intermediate results through the photonic fabric
    """
    for i in range(M):
        for j in range(N):
            acc: float32 = 0.0
            for k in range(K):
                acc += A[i * K + k] * B[k * N + j]
            C[i * N + j] = acc


# ---------------------------------------------------------------------------
# AOT compile and save
# ---------------------------------------------------------------------------

print("=" * 60)
print("AOT compiling matmul_kernel ...")
print("=" * 60)

aot_bytes = matmul_kernel.aot_compile()
print(f"AOT binary size:  {len(aot_bytes)} bytes")
print(f"Magic:            {aot_bytes[:4]}")

# Save to disk
with open("/tmp/matmul.lrnpu", "wb") as f:
    f.write(aot_bytes)
print("Written to: /tmp/matmul.lrnpu")

# ---------------------------------------------------------------------------
# Bundle as Fat Binary (supports multiple NCE generations)
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("Building Fat Binary (gen1 + gen2) ...")
print("=" * 60)

opts_gen1 = CompileOptions(mode="aot", nce_generation=1)
opts_gen2 = CompileOptions(mode="aot", nce_generation=2)

result_gen1 = CompilationPipeline(opts_gen1).compile_function(matmul_kernel.__wrapped__)
result_gen2 = CompilationPipeline(opts_gen2).compile_function(matmul_kernel.__wrapped__)

import pickle
host_bytes = pickle.dumps(matmul_kernel.__wrapped__)

fat = FatBinaryBundler().bundle(
    name="matmul",
    host_bytes=host_bytes,
    device_blobs={
        1: result_gen1.lrbs_bytes,
        2: result_gen2.lrbs_bytes,
    },
    manifest_extra={
        "description": "Tiled matrix multiply for LightRail NCE",
        "tile_size": "64x64",
    },
)

with open("/tmp/matmul.lrfat", "wb") as f:
    f.write(fat)

print(f"Fat binary size:  {len(fat)} bytes")
print(f"Written to:       /tmp/matmul.lrfat")

# ---------------------------------------------------------------------------
# Compilation summary
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("Compilation report:")
print("=" * 60)
print(result_gen1.summary())

# Show WDM channel usage
fn = result_gen1.module.get_function("matmul_kernel")
if fn:
    channels_used = fn.attrs.get("wdm_channels_used", "N/A")
    num_tiles     = fn.attrs.get("num_tiles", "N/A")
    print(f"\nWDM channels used: {channels_used}")
    print(f"Fabric tiles used: {num_tiles}")
    print("(No CUDA warp scheduling — deterministic optical dispatch)")

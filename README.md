# LightRail Photonic Compiler

A 6-stage compiler that translates Python (PyTorch/JAX-style) and C++ code into
optimised machine code for the **LightRail Neural Compute Engine (NCE)** and its
20-layer photonic interconnect fabric.

---

## Architecture Overview

```
Python / C++ source
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Stage 1 │ AST Parsing & High-Level IR                                   │
│          │  - @lightrail.jit decorator parses Python AST                  │
│          │  - Splits into Host (CPU) and Device (NCE) functions           │
│          │  - Produces SSA-form high-level IR                             │
├──────────────────────────────────────────────────────────────────────────┤
│  Stage 2 │ Type Inference & Lowering                                      │
│          │  - Strict type inference: int32, float32, FP8, ABFP16, ...     │
│          │  - Constant folding and initial dead code elimination          │
├──────────────────────────────────────────────────────────────────────────┤
│  Stage 3 │ Photonic-Aware Optimisation Passes                             │
│          │  - Alias analysis, loop splitting (tile pipeline stages)       │
│          │  - Fused Multiply-Add (FMA) fusion                             │
│          │  - Graph partitioning across 20 fabric layers                  │
│          │  - Collective interception (All-Reduce -> photonic ring)       │
├──────────────────────────────────────────────────────────────────────────┤
│  Stage 4 │ Dataflow & Wavelength Mapping  (replaces CUDA threads)         │
│          │  - 64 WDM channels = 64 deterministic virtual processors       │
│          │  - Static channel assignment at compile time (no warp sched.)  │
│          │  - Dataflow routing across the 20-layer optical mesh            │
├──────────────────────────────────────────────────────────────────────────┤
│  Stage 5 │ Tile Bytecode & Fat Binary Generation                          │
│          │  - .lrbs bytecode: portable 64-bit instruction words           │
│          │  - .lrfat fat binary: multi-generation device blobs + host code│
├──────────────────────────────────────────────────────────────────────────┤
│  Stage 6 │ Execution & Fabric OS Handoff                                  │
│          │  - AOT: compile to .lrnpu native NCE binary                    │
│          │  - JIT: on-demand compile + cache (<200 ns on cache hit)       │
│          │  - Fabric OS Global Scheduler: deterministic dispatch           │
└──────────────────────────────────────────────────────────────────────────┘
```

## Key Divergences from CUDA

| Feature              | CUDA                          | LightRail                               |
|----------------------|-------------------------------|-----------------------------------------|
| Parallelism model    | Grids / blocks / warps        | 64 WDM wavelength channels (static)     |
| Scheduling           | Hardware warp scheduler       | Deterministic compile-time assignment   |
| Memory hierarchy     | Registers -> shared -> HBM    | Flat fabric SRAM + direct cross-chip DMA|
| Collective ops       | NCCL over NVLink              | Photonic ring-reduce on Layer 19        |
| Compute precision    | FP32 / FP16 / INT8            | + Ternary {-1,0,+1} + Analog wave       |
| Dispatch latency     | us-ms kernel launch overhead  | <100 ns optical switch programming      |

---

## Quick Start

### Python API

```python
import lightrail

@lightrail.jit
def dot_product(A: "float32", B: "float32", N: "int32") -> "float32":
    acc: float32 = 0.0
    for i in range(N):
        acc += A[i] * B[i]
    return acc

# First call: compile -> .lrbs -> dispatch via Fabric OS
result = dot_product(a_buf, b_buf, 1024)

# Subsequent calls: cache hit, direct dispatch
result = dot_product(a_buf, b_buf, 1024)
```

### AOT Compilation

```python
@lightrail.jit(mode="aot")
def inference_kernel(weights, activations, N: "int32") -> "float32":
    ...

# Compile and save binary for production deployment
aot_bytes = inference_kernel.aot_compile()
with open("kernel.lrnpu", "wb") as f:
    f.write(aot_bytes)
```

### IR Introspection

```python
@lightrail.jit
def kernel(a, b):
    return a + b

print(kernel.ir())   # prints the SSA IR after all optimisation passes
```

### C++ Tiled Pipeline Library

```cpp
#include <lightrail/lightrail.hpp>

__lr_device__ void my_kernel(const float* A, const float* B, float* C, int N) {
    lr_wdm_bind(0);   // bind to WDM channel 0, no warp scheduler

    lr::TiledLoop<2>(N, 64,
        [&](int i) { /* LOAD: DMA tile into SRAM */    },
        [&](int i) { /* COMPUTE: FMA over tile */      },
        [&](int i) { /* STORE: DMA result to fabric */ }
    );
}
```

---

## LightRail Native Types

| Type      | Bits | Description                                    |
|-----------|------|------------------------------------------------|
| `fp32`    | 32   | Standard IEEE 754 single precision             |
| `fp16`    | 16   | Half precision                                 |
| `bf16`    | 16   | Brain float 16                                 |
| `abfp16`  | 16   | Adaptive Block Floating Point 16 (LightRail)   |
| `fp8`     | 8    | 8-bit float (E4M3 / E5M2)                      |
| `ternary` | 2    | {-1, 0, +1} -> optical power levels (Layers 1-5)|
| `analog`  | 32   | Continuous amplitude MZI wave (Layers 6-7)     |

---

## Installation

```bash
pip install lightrail-compiler
```

Or from source:

```bash
git clone <repo>
cd LightOS_Compiler
pip install -e ".[dev]"
```

## CLI

```bash
lrc compile kernel.py --fn dot_product --mode jit
lrc compile kernel.py --fn matmul --mode aot -o matmul.lrnpu
lrc inspect matmul.lrnpu
lrc ir kernel.py --fn dot_product
```

## Running Tests

```bash
pytest tests/ -v
```

75 tests covering all 6 pipeline stages.

---

## Project Structure

```
lightrail/
├── ir/                   # Types, opcodes, SSA IR, builder
├── frontend/             # Python AST parser, host/device splitter
├── passes/               # Optimisation passes (Stages 2-3)
│   ├── type_inference.py
│   ├── dead_code.py
│   ├── alias_analysis.py
│   ├── loop_splitting.py
│   ├── fma_fusion.py
│   └── graph_partition.py
├── dataflow/             # WDM mapping, routing, collective intercept (Stage 4)
├── codegen/              # Bytecode, fat binary, ternary encoding (Stage 5)
├── runtime/              # AOT, JIT, Fabric OS interface (Stage 6)
├── cpp/                  # C++ header-only library
├── pipeline.py           # 6-stage pipeline orchestrator
├── decorators.py         # @lightrail.jit decorator
└── cli.py                # lrc CLI tool
examples/
├── 01_hello_lightrail.py
├── 02_matmul_aot.py
├── 03_ternary_analog.py
└── 04_cpp_pipeline.cpp
tests/
├── test_ir.py
├── test_frontend.py
├── test_passes.py
├── test_dataflow.py
├── test_codegen.py
└── test_pipeline.py
```

/**
 * Example 04: C++ Tiled Software Pipelining
 * ==========================================
 * Demonstrates the LightRail C++ library for writing device kernels with
 * explicit tiled software pipelining.
 *
 * Key features shown:
 *   - LRTile<float, 64, 64>  — 2D tile type in SRAM
 *   - lr::TiledLoop<>        — explicit pipeline: Load -> Compute -> Store
 *   - lr::lr_wdm_bind()      — bind to a WDM channel (no warp scheduling)
 *   - lr::lr_dma_load/store  — SRAM-to-SRAM DMA bypassing HBM
 *   - lr::lr_ternary_dot()   — native ternary dot product
 *
 * Build (once the LightRail toolchain is available):
 *   lrc++ -target lightrail-nce-gen1 -O2 04_cpp_pipeline.cpp -o pipeline.lrnpu
 *
 * Simulate on host:
 *   g++ -std=c++17 -I../lightrail/cpp -O2 04_cpp_pipeline.cpp -o pipeline_host
 */

#include "../lightrail/cpp/lightrail.hpp"
#include "../lightrail/cpp/intrinsics.hpp"

#include <cstdio>
#include <cstring>
#include <cmath>

using namespace lr;

// ---------------------------------------------------------------------------
// Tile dimensions
// ---------------------------------------------------------------------------

constexpr int TILE_M = 64;
constexpr int TILE_N = 64;
constexpr int TILE_K = 64;

// ---------------------------------------------------------------------------
// Helper: print a small tile excerpt
// ---------------------------------------------------------------------------

static void print_tile_excerpt(const LRTile<float, 4, 4>& tile, const char* name) {
    printf("  %s[0:4, 0:4]:\n", name);
    for (int r = 0; r < 4; ++r) {
        printf("    [");
        for (int c = 0; c < 4; ++c) {
            printf("%7.3f", tile.at(r, c));
            if (c < 3) printf(", ");
        }
        printf("]\n");
    }
}

// ---------------------------------------------------------------------------
// Example 1: Tiled matrix multiply with explicit software pipelining
// ---------------------------------------------------------------------------

__lr_device__
void tiled_matmul(
    const float* __restrict__ A,    // [M, K]
    const float* __restrict__ B,    // [K, N]
          float* __restrict__ C,    // [M, N]
    int M, int N, int K)
{
    // Bind to WDM channel 0 (deterministic, no warp scheduler needed)
    uint32_t ch = lr_wdm_bind(0);

    // Double-buffered tile SRAM: ping-pong between buffer A and B
    LRTile<float, TILE_M, TILE_K> A_sram[2];
    LRTile<float, TILE_K, TILE_N> B_sram[2];
    LRTile<float, TILE_M, TILE_N> C_sram;

    // Zero-initialise accumulator
    memset(C_sram.data, 0, sizeof(C_sram.data));

    int num_k_tiles = (K + TILE_K - 1) / TILE_K;

    // Use TiledLoop for automatic prologue/epilogue and prefetch scheduling
    lr::TiledLoop<2>(
        num_k_tiles, 1,
        // LOAD STAGE: DMA the next K-tile from fabric memory into SRAM
        [&](int k_tile) {
            int buf = k_tile & 1;  // alternate between double buffers
            int k0  = k_tile * TILE_K;

            // Prefetch A[0:M, k0:k0+TILE_K]
            for (int r = 0; r < TILE_M; ++r) {
                lr_dma_load(
                    A_sram[buf].row_ptr(r),
                    &A[r * K + k0],
                    TILE_K * sizeof(float),
                    ch
                );
            }
            // Prefetch B[k0:k0+TILE_K, 0:N]
            for (int k = 0; k < TILE_K; ++k) {
                lr_dma_load(
                    B_sram[buf].row_ptr(k),
                    &B[(k0 + k) * N],
                    TILE_N * sizeof(float),
                    ch
                );
            }
        },
        // COMPUTE STAGE: FMA reduction over the K tile (runs while next load is in-flight)
        [&](int k_tile) {
            int buf = k_tile & 1;
            for (int m = 0; m < TILE_M; ++m) {
                for (int n = 0; n < TILE_N; ++n) {
                    float acc = C_sram.at(m, n);
                    for (int k = 0; k < TILE_K; ++k) {
                        acc += A_sram[buf].at(m, k) * B_sram[buf].at(k, n);
                    }
                    C_sram.at(m, n) = acc;
                }
            }
        },
        // STORE STAGE: DMA result tile back to fabric memory
        [&](int k_tile) {
            if (k_tile == num_k_tiles - 1) {  // only on last K tile
                for (int m = 0; m < TILE_M; ++m) {
                    lr_dma_store(
                        &C[m * N],
                        C_sram.row_ptr(m),
                        TILE_N * sizeof(float),
                        ch
                    );
                }
            }
        }
    );
}

// ---------------------------------------------------------------------------
// Example 2: Ternary inference kernel (Layer 1-5 compute)
// ---------------------------------------------------------------------------

__lr_device__
int32_t ternary_linear(
    const uint64_t* weights_packed,   // ternary weights (2 bits/sym, 32/word)
    const int8_t*   activations,      // ternary activations
    int             n_weights)
{
    // Bind to a dedicated WDM channel for ternary ops (channel 8 = Layer 2)
    lr_wdm_bind(8);

    int32_t accumulator = 0;
    int n_words = (n_weights + 31) / 32;

    for (int w = 0; w < n_words; ++w) {
        // Pack 32 activation symbols into one word
        uint64_t act_word = 0;
        int base = w * 32;
        for (int i = 0; i < 32 && base + i < n_weights; ++i) {
            int8_t a = activations[base + i];
            uint8_t enc = (a == -1) ? 0u : (a == 0) ? 1u : 2u;
            act_word |= (uint64_t(enc) << (2 * i));
        }
        int n_sym = (w == n_words - 1) ? (n_weights - base) : 32;
        // Native ternary dot product (single optical cycle on NCE)
        accumulator += lr_ternary_dot(weights_packed[w], act_word, n_sym);
    }
    return accumulator;
}

// ---------------------------------------------------------------------------
// Host simulation entry point
// ---------------------------------------------------------------------------

int main() {
    printf("LightRail C++ Tiled Pipeline — Host Simulation\n");
    printf("================================================\n\n");

    // --- Ternary example ---
    printf("Ternary linear layer example:\n");

    constexpr int N_WEIGHTS = 64;
    int8_t weights_raw[N_WEIGHTS];
    int8_t activations[N_WEIGHTS];

    // Fill with example ternary values
    for (int i = 0; i < N_WEIGHTS; ++i) {
        weights_raw[i] = (i % 3) - 1;    // pattern: -1, 0, +1, -1, 0, +1, ...
        activations[i] = (i % 2 == 0) ? 1 : -1;
    }

    // Pack weights
    uint64_t packed[2];
    packed[0] = intrinsics::pack_ternary32(weights_raw);
    packed[1] = intrinsics::pack_ternary32(weights_raw + 32);

    int32_t result = ternary_linear(packed, activations, N_WEIGHTS);
    printf("  Result of ternary dot (64 weights): %d\n\n", result);

    // --- WDM channel frequencies ---
    printf("WDM Channel Frequency Grid (first 8 channels):\n");
    printf("  %-12s %-20s %-16s\n", "Channel", "Frequency (THz)", "Wavelength (nm)");
    printf("  %s\n", std::string(50, '-').c_str());
    for (int ch = 0; ch < 8; ++ch) {
        printf("  %-12d %-20.4f %-16.2f\n",
               ch,
               intrinsics::wdm_frequency_thz(ch),
               intrinsics::wdm_wavelength_nm(ch));
    }

    // --- MZI phase table ---
    printf("\nMZI Phase Table (Analog Layer 6-7):\n");
    printf("  %-10s %-18s %-16s\n", "Weight", "Phase (rad)", "Transmission");
    printf("  %s\n", std::string(48, '-').c_str());
    float test_weights[] = {0.0f, 0.1f, 0.25f, 0.5f, 0.75f, 0.9f, 1.0f};
    for (float w : test_weights) {
        float phase = intrinsics::mzi_phase_for_weight(w);
        float transmission = intrinsics::mzi_transmission(phase);
        printf("  %-10.2f %-18.6f %-16.6f\n", w, phase, transmission);
    }

    printf("\nSimulation complete. (On NCE hardware, kernels dispatch in <100 ns)\n");
    return 0;
}

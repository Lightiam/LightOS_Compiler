/**
 * LightRail C++ Tiled Software Pipelining Library
 * =================================================
 * Header-only C++ library providing templated types and intrinsics for
 * writing high-performance device kernels targeting the LightRail NCE.
 *
 * Key features:
 *   - Built-in vector types: LRVec<T, N>, LRTile<T, Rows, Cols>
 *   - Explicit tiled software pipelining: Pipeline<Load, Compute, Store>
 *   - Automatic DMA prefetching and loop unrolling (via compiler pragmas)
 *   - WDM channel binding intrinsics: lr_wdm_bind(), lr_wdm_route()
 *   - Ternary and analog compute intrinsics
 *   - SRAM / fabric memory DMA helpers bypassing HBM
 *
 * Usage:
 *   #include <lightrail/lightrail.hpp>
 *
 *   __lr_device__ void matmul_kernel(
 *       const LRTile<float, 64, 64>* A,
 *       const LRTile<float, 64, 64>* B,
 *             LRTile<float, 64, 64>* C)
 *   {
 *       using Pipe = lr::Pipeline<
 *           lr::LoadStage<LRTile<float,64,64>>,
 *           lr::ComputeStage<lr::FMAReduce>,
 *           lr::StoreStage<LRTile<float,64,64>>
 *       >;
 *       Pipe::run(A, B, C);
 *   }
 */

#pragma once

#include <cstdint>
#include <cstddef>
#include <type_traits>
#include <array>
#include <utility>

// ---------------------------------------------------------------------------
// Compiler / target detection macros
// ---------------------------------------------------------------------------

#if defined(__LIGHTRAIL_NCE__)
#   define __lr_device__   __attribute__((lr_device))
#   define __lr_host__     __attribute__((lr_host))
#   define __lr_both__     __attribute__((lr_device, lr_host))
#   define LR_INLINE       __attribute__((always_inline)) inline
#else
// Fallback for host-side testing / simulation
#   define __lr_device__
#   define __lr_host__
#   define __lr_both__
#   define LR_INLINE       inline
#endif

// ---------------------------------------------------------------------------
// WDM Channel constants
// ---------------------------------------------------------------------------

namespace lr {

constexpr int NUM_WDM_CHANNELS = 64;
constexpr int FABRIC_LAYERS    = 20;
constexpr int SRAM_SIZE_KB     = 512;     // per-tile SRAM

// ---------------------------------------------------------------------------
// Scalar type aliases matching the LightRail type system
// ---------------------------------------------------------------------------

using fp32_t  = float;
using fp16_t  = uint16_t;   // stored as raw half bits
using bf16_t  = uint16_t;
using fp8_t   = uint8_t;
using int8_t  = ::int8_t;
using int32_t = ::int32_t;
using int64_t = ::int64_t;

// Ternary: packed 2 bits per element in a 64-bit word
struct ternary_t {
    int8_t val;   // {-1, 0, +1}
    constexpr ternary_t(int8_t v = 0) : val(v) {}
    constexpr operator int8_t() const { return val; }
};

// ---------------------------------------------------------------------------
// LRVec<T, N> — Fixed-width SIMD vector on a single WDM channel
// ---------------------------------------------------------------------------

template<typename T, int N>
struct LRVec {
    static_assert(N > 0 && (N & (N - 1)) == 0, "N must be a power of 2");
    static constexpr int lanes = N;
    using element_type = T;

    T data[N] = {};

    LR_INLINE __lr_both__ T& operator[](int i)       { return data[i]; }
    LR_INLINE __lr_both__ const T& operator[](int i) const { return data[i]; }

    // Element-wise operations
    LR_INLINE __lr_both__ LRVec operator+(const LRVec& rhs) const {
        LRVec r;
        for (int i = 0; i < N; ++i) r.data[i] = data[i] + rhs.data[i];
        return r;
    }
    LR_INLINE __lr_both__ LRVec operator*(const LRVec& rhs) const {
        LRVec r;
        for (int i = 0; i < N; ++i) r.data[i] = data[i] * rhs.data[i];
        return r;
    }
    LR_INLINE __lr_both__ LRVec operator-(const LRVec& rhs) const {
        LRVec r;
        for (int i = 0; i < N; ++i) r.data[i] = data[i] - rhs.data[i];
        return r;
    }

    // Fused multiply-add: a * b + c
    LR_INLINE __lr_both__
    static LRVec fma(const LRVec& a, const LRVec& b, const LRVec& c) {
        LRVec r;
        for (int i = 0; i < N; ++i)
            r.data[i] = a.data[i] * b.data[i] + c.data[i];
        return r;
    }

    // Horizontal reduction (sum)
    LR_INLINE __lr_both__ T reduce_sum() const {
        T acc = T{};
        for (int i = 0; i < N; ++i) acc += data[i];
        return acc;
    }
};

// Convenience aliases
using Vec8f  = LRVec<fp32_t, 8>;
using Vec16f = LRVec<fp32_t, 16>;
using Vec32f = LRVec<fp32_t, 32>;
using Vec64f = LRVec<fp32_t, 64>;
using Vec32i = LRVec<int32_t, 32>;

// ---------------------------------------------------------------------------
// LRTile<T, Rows, Cols> — 2D tile in SRAM
// ---------------------------------------------------------------------------

template<typename T, int Rows, int Cols>
struct LRTile {
    static constexpr int rows = Rows;
    static constexpr int cols = Cols;
    static constexpr int size = Rows * Cols;
    using element_type = T;

    T data[Rows * Cols] = {};

    LR_INLINE __lr_both__ T& at(int r, int c)       { return data[r * Cols + c]; }
    LR_INLINE __lr_both__ const T& at(int r, int c) const { return data[r * Cols + c]; }

    LR_INLINE __lr_both__ T* row_ptr(int r)       { return &data[r * Cols]; }
    LR_INLINE __lr_both__ const T* row_ptr(int r) const { return &data[r * Cols]; }
};

// ---------------------------------------------------------------------------
// DMA helpers (SRAM <-> fabric memory, bypassing HBM)
// ---------------------------------------------------------------------------

/**
 * lr_dma_load: Asynchronously load 'bytes' from 'src' (fabric/remote SRAM)
 *              to 'dst' (local SRAM).  Returns a completion token.
 */
LR_INLINE __lr_device__
uint32_t lr_dma_load(void* dst, const void* src, size_t bytes, int channel = 0) {
#if defined(__LIGHTRAIL_NCE__)
    return __builtin_lr_dma_load(dst, src, bytes, channel);
#else
    // Host simulation: memcpy
    __builtin_memcpy(dst, src, bytes);
    return 0u;
#endif
}

/**
 * lr_dma_store: Asynchronously write 'bytes' from local SRAM to 'dst'.
 */
LR_INLINE __lr_device__
uint32_t lr_dma_store(void* dst, const void* src, size_t bytes, int channel = 0) {
#if defined(__LIGHTRAIL_NCE__)
    return __builtin_lr_dma_store(dst, src, bytes, channel);
#else
    __builtin_memcpy(dst, src, bytes);
    return 0u;
#endif
}

/**
 * lr_dma_sync: Wait for all DMA operations on a channel to complete.
 */
LR_INLINE __lr_device__
void lr_dma_sync(int channel = 0) {
#if defined(__LIGHTRAIL_NCE__)
    __builtin_lr_dma_sync(channel);
#endif
}

/**
 * lr_prefetch: Issue a prefetch hint for the next tile (software pipelining).
 *              The compiler uses this to overlap DMA with computation.
 */
LR_INLINE __lr_device__
void lr_prefetch(const void* addr, size_t bytes, int distance = 2) {
#if defined(__LIGHTRAIL_NCE__)
    __builtin_lr_prefetch(addr, bytes, distance);
#else
    __builtin_prefetch(addr, 0, distance);
#endif
}

// ---------------------------------------------------------------------------
// WDM Intrinsics
// ---------------------------------------------------------------------------

/**
 * lr_wdm_bind: Bind the current execution stream to WDM channel 'ch'.
 *              Returns the channel handle (opaque on device).
 */
LR_INLINE __lr_device__
uint32_t lr_wdm_bind(int channel) {
#if defined(__LIGHTRAIL_NCE__)
    return __builtin_lr_wdm_bind(channel);
#else
    return static_cast<uint32_t>(channel);
#endif
}

/**
 * lr_wdm_route: Route a data buffer to another WDM channel/node.
 */
LR_INLINE __lr_device__
void lr_wdm_route(uint32_t src_ch, uint32_t dst_ch, const void* data, size_t bytes) {
#if defined(__LIGHTRAIL_NCE__)
    __builtin_lr_wdm_route(src_ch, dst_ch, data, bytes);
#endif
}

/**
 * lr_fabric_sync: Global barrier across all WDM channels.
 */
LR_INLINE __lr_device__
void lr_fabric_sync() {
#if defined(__LIGHTRAIL_NCE__)
    __builtin_lr_fabric_sync();
#endif
}

// ---------------------------------------------------------------------------
// Ternary Intrinsics
// ---------------------------------------------------------------------------

/**
 * lr_ternary_dot: Native ternary dot product (hardware accumulation).
 * Operates on packed ternary words (2 bits/symbol, 32 symbols per uint64_t).
 */
LR_INLINE __lr_device__
int32_t lr_ternary_dot(uint64_t a, uint64_t b, int n_symbols) {
#if defined(__LIGHTRAIL_NCE__)
    return __builtin_lr_ternary_dot(a, b, n_symbols);
#else
    int32_t acc = 0;
    for (int i = 0; i < n_symbols && i < 32; ++i) {
        int8_t ai = ((a >> (2*i)) & 0x3) - 1;  // decode: 0->-1, 1->0, 2->+1
        int8_t bi = ((b >> (2*i)) & 0x3) - 1;
        acc += ai * bi;
    }
    return acc;
#endif
}

// ---------------------------------------------------------------------------
// Software Pipeline: Stage tags and Pipeline<> template
// ---------------------------------------------------------------------------

struct LoadTag    {};
struct ComputeTag {};
struct StoreTag   {};

/**
 * TiledLoop: Utility for declaring an explicitly tiled, pipelined loop.
 *
 * Expands to:
 *   - Prologue: prefetch tile[0]
 *   - Steady state: process tile[i] while prefetching tile[i+1]
 *   - Epilogue: process remaining tile[N-1]
 *
 * The compiler automatically generates the prologue/epilogue; the developer
 * only declares the three stage lambdas.
 *
 * Usage:
 *   lr::TiledLoop<64>(N, tile_size,
 *       [&](int i) { /* load stage: DMA tile i into SRAM */ },
 *       [&](int i) { /* compute stage: process SRAM tile */ },
 *       [&](int i) { /* store stage: DMA result out */ }
 *   );
 */
template<int PrefetchDistance = 2, typename LoadFn, typename ComputeFn, typename StoreFn>
LR_INLINE __lr_device__
void TiledLoop(int n, int tile_size, LoadFn load, ComputeFn compute, StoreFn store) {
    int num_tiles = (n + tile_size - 1) / tile_size;

    // Prologue: issue first PrefetchDistance loads
    for (int p = 0; p < PrefetchDistance && p < num_tiles; ++p) {
        load(p);
    }

    // Steady state
    for (int i = 0; i < num_tiles; ++i) {
        // Prefetch future tile
        int pf = i + PrefetchDistance;
        if (pf < num_tiles) {
            load(pf);
        }
        lr_dma_sync();

        // Compute on current tile
        compute(i);
        lr_dma_sync();

        // Store result
        store(i);
    }
}

} // namespace lr

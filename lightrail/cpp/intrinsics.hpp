/**
 * LightRail NCE Intrinsics Reference
 * ====================================
 * Low-level intrinsic declarations for the LightRail Neural Compute Engine.
 *
 * These map directly to NCE hardware instructions.  On non-NCE targets they
 * are emulated in software (performance not guaranteed).
 *
 * Include via:  #include <lightrail/intrinsics.hpp>
 * (Usually you should include <lightrail/lightrail.hpp> instead, which
 *  includes this automatically.)
 */

#pragma once
#include <cstdint>
#include <cstddef>

// ---------------------------------------------------------------------------
// Ternary weight packing helpers
// ---------------------------------------------------------------------------

namespace lr {
namespace intrinsics {

/**
 * pack_ternary32: Pack 32 ternary symbols {-1, 0, +1} into a 64-bit word.
 * Encoding: 0b00 = -1, 0b01 = 0, 0b10 = +1.
 */
inline uint64_t pack_ternary32(const int8_t* symbols) {
    uint64_t word = 0;
    for (int i = 0; i < 32; ++i) {
        uint8_t enc = (symbols[i] == -1) ? 0u : (symbols[i] == 0) ? 1u : 2u;
        word |= (uint64_t(enc) << (2 * i));
    }
    return word;
}

/**
 * unpack_ternary32: Decode a 64-bit packed ternary word into 32 int8 values.
 */
inline void unpack_ternary32(uint64_t word, int8_t* out) {
    static constexpr int8_t lut[4] = {-1, 0, 1, 0};
    for (int i = 0; i < 32; ++i) {
        out[i] = lut[(word >> (2 * i)) & 0x3];
    }
}

// ---------------------------------------------------------------------------
// Analog MZI helpers
// ---------------------------------------------------------------------------

/**
 * mzi_transmission: Compute the intensity transmission of an ideal MZI
 *                   given phase shift phi (radians).
 * T = cos^2(phi / 2)
 */
inline float mzi_transmission(float phi) {
    float half = phi * 0.5f;
    // cos^2 via 1 - sin^2 to avoid trig where possible
    float c = __builtin_cosf(half);
    return c * c;
}

/**
 * mzi_phase_for_weight: Inverse of mzi_transmission.
 * phi = 2 * arccos(sqrt(|w|))
 */
inline float mzi_phase_for_weight(float w) {
    if (w < 0.0f) w = -w;
    if (w > 1.0f) w = 1.0f;
    return 2.0f * __builtin_acosf(__builtin_sqrtf(w));
}

// ---------------------------------------------------------------------------
// Optical power level encoding for ternary
// ---------------------------------------------------------------------------

// Normalised optical power levels
constexpr float LR_POWER_OFF  = 0.0f;    // -1
constexpr float LR_POWER_LOW  = 0.333f;  //  0
constexpr float LR_POWER_HIGH = 1.0f;    // +1

inline float ternary_to_power(int8_t t) {
    if (t >  0) return LR_POWER_HIGH;
    if (t == 0) return LR_POWER_LOW;
    return LR_POWER_OFF;
}

inline int8_t power_to_ternary(float p, float threshold_hi = 0.66f,
                                         float threshold_lo = 0.16f) {
    if (p >= threshold_hi) return  1;
    if (p <= threshold_lo) return -1;
    return 0;
}

// ---------------------------------------------------------------------------
// WDM frequency grid (100 GHz ITU C-band)
// ---------------------------------------------------------------------------

constexpr double C_BAND_BASE_THz    = 193.1;
constexpr double CHANNEL_SPACING_THz = 0.1;
constexpr int    NUM_CHANNELS        = 64;

inline double wdm_frequency_thz(int channel_id) {
    return C_BAND_BASE_THz + channel_id * CHANNEL_SPACING_THz;
}

inline double wdm_wavelength_nm(int channel_id) {
    // lambda = c / f;  c ~ 3e8 m/s
    double f_hz = (C_BAND_BASE_THz + channel_id * CHANNEL_SPACING_THz) * 1e12;
    return (3.0e8 / f_hz) * 1e9;   // nm
}

// ---------------------------------------------------------------------------
// Collective reduction operations (intercepted by Fabric OS)
// ---------------------------------------------------------------------------

/**
 * lr_all_reduce_sum: Fabric-wide sum reduction over all WDM channels.
 * The compiler intercepts this call and maps it to the photonic ring-reduce
 * on layer 19 of the fabric.
 */
template<typename T>
__attribute__((lr_collective))
inline T lr_all_reduce_sum(T local_val) {
#if defined(__LIGHTRAIL_NCE__)
    return __builtin_lr_all_reduce_sum(local_val);
#else
    // Host simulation: return value unchanged (single node)
    return local_val;
#endif
}

/**
 * lr_broadcast: Broadcast a value from channel 0 to all channels.
 */
template<typename T>
__attribute__((lr_collective))
inline T lr_broadcast(T val, int src_channel = 0) {
#if defined(__LIGHTRAIL_NCE__)
    return __builtin_lr_broadcast(val, src_channel);
#else
    return val;
#endif
}

} // namespace intrinsics
} // namespace lr

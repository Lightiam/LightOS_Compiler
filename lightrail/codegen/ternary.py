"""
Ternary & Analog Encoding
===========================
Encodes IR instructions that operate on LightRail's native photonic compute
modes:

  - Ternary Logic (Layers 1–5): values in {-1, 0, +1} mapped to three
    distinct optical power levels (OFF, LOW, HIGH).

  - Analog Wave Compute (Layers 6–7): continuous-amplitude optical signals
    processed via coherent detection and MZI (Mach-Zehnder Interferometer)
    arrays.

This module provides:
  1. Float-to-ternary quantisation (stochastic rounding or deterministic).
  2. Ternary arithmetic encoding for the bytecode emitter.
  3. Analog wave parameter extraction for the WDM mapper.
  4. An IR pass that inserts TERNARY_ENCODE / TERNARY_DECODE instructions
     around ternary compute regions.
"""

from __future__ import annotations
import math
from typing import List, Sequence, Tuple

from lightrail.ir.ssa import Module, Function, Instruction, BasicBlock
from lightrail.ir.ops import Opcode
from lightrail.ir.types import TERNARY, ANALOG, FP32, VOID


# ---------------------------------------------------------------------------
# Ternary value representation
# ---------------------------------------------------------------------------

# Optical power levels (normalised)
TERNARY_MINUS_ONE = 0   # OFF state (no photon)
TERNARY_ZERO      = 1   # LOW power  (~0.3 × P_max)
TERNARY_PLUS_ONE  = 2   # HIGH power (~1.0 × P_max)

_ENCODE = {-1: TERNARY_MINUS_ONE, 0: TERNARY_ZERO, 1: TERNARY_PLUS_ONE}
_DECODE = {v: k for k, v in _ENCODE.items()}


def quantise_to_ternary(values: Sequence[float], threshold: float = 0.5) -> List[int]:
    """
    Quantise a sequence of floats to ternary symbols using a threshold.

    Args:
        values    : Input floating-point values.
        threshold : Absolute value above which output is ±1 (default 0.5).

    Returns:
        List of ternary symbols in {-1, 0, +1}.
    """
    result = []
    for v in values:
        if v > threshold:
            result.append(1)
        elif v < -threshold:
            result.append(-1)
        else:
            result.append(0)
    return result


def ternary_to_float(symbols: Sequence[int]) -> List[float]:
    """Convert ternary symbols back to float for dequantisation."""
    return [float(s) for s in symbols]


def ternary_dot(a: Sequence[int], b: Sequence[int]) -> int:
    """
    Native ternary dot product.  In hardware this is realised as a
    sign-magnitude sum over optical power levels.
    """
    return sum(ai * bi for ai, bi in zip(a, b))


def pack_ternary_word(symbols: Sequence[int]) -> int:
    """
    Pack up to 32 ternary symbols into a 64-bit integer using 2 bits each.
    Encoding: 00 = -1, 01 = 0, 10 = +1.
    """
    word = 0
    for i, s in enumerate(symbols[:32]):
        encoded = _ENCODE.get(s, TERNARY_ZERO)
        word |= (encoded & 0x3) << (i * 2)
    return word


def unpack_ternary_word(word: int, count: int) -> List[int]:
    """Unpack ternary symbols from a 64-bit integer."""
    result = []
    for i in range(count):
        encoded = (word >> (i * 2)) & 0x3
        result.append(_DECODE.get(encoded, 0))
    return result


# ---------------------------------------------------------------------------
# Analog Wave parameters
# ---------------------------------------------------------------------------

def mzi_phase_for_weight(weight: float) -> float:
    """
    Compute the MZI phase shift (in radians) required to implement a
    given weight in the analog wave compute layer.

    For an ideal 2×2 MZI beamsplitter, the transmission is cos²(θ/2),
    so we solve: cos²(θ/2) = |weight| and θ = 2 * arccos(sqrt(|weight|)).
    """
    w = min(abs(weight), 1.0)
    return 2.0 * math.acos(math.sqrt(w))


def analog_amplitude_for_bias(bias: float, v_pi: float = 3.5) -> float:
    """
    Electro-optic modulator driving voltage for a given bias value.
    V = bias * V_pi where V_pi is the half-wave voltage (~3.5 V typical).
    """
    return bias * v_pi


# ---------------------------------------------------------------------------
# IR Pass: insert TERNARY_ENCODE / TERNARY_DECODE around ternary ops
# ---------------------------------------------------------------------------

_TERNARY_OPS = {Opcode.TADD, Opcode.TMUL, Opcode.TDOT}
_ANALOG_OPS  = {Opcode.WAVE_MOD, Opcode.WAVE_DEMOD, Opcode.WAVE_PHASE,
                Opcode.WAVE_INTERFERE, Opcode.WAVE_ATTENUATE}


class TernaryEncodingPass:
    """
    Wraps ternary compute operations with encode/decode instructions,
    and annotates analog ops with MZI phase parameters.
    """

    def run(self, module: Module) -> Module:
        for fn in module.functions:
            for bb in fn.blocks:
                self._process_block(bb, fn)
        return module

    def _process_block(self, bb: BasicBlock, fn: Function) -> None:
        new_instrs: List[Instruction] = []
        encode_cache: dict[str, str] = {}   # original SSA -> encoded SSA

        for instr in bb.instructions:
            if instr.op in _TERNARY_OPS:
                # Insert TERNARY_ENCODE for each float operand
                encoded_ops = []
                for op in instr.operands:
                    if op in encode_cache:
                        encoded_ops.append(encode_cache[op])
                    else:
                        enc_name = f"_tenc_{op}"
                        enc_instr = Instruction(
                            op=Opcode.TERNARY_ENCODE,
                            result=enc_name,
                            operands=[op],
                            attrs={"threshold": 0.5},
                            type_=TERNARY,
                        )
                        new_instrs.append(enc_instr)
                        encode_cache[op] = enc_name
                        encoded_ops.append(enc_name)
                        fn.values._table[enc_name] = TERNARY

                # Emit ternary op with encoded operands
                ternary_result = f"_t_{instr.result}" if instr.result else None
                ternary_instr = Instruction(
                    op=instr.op,
                    result=ternary_result,
                    operands=encoded_ops,
                    attrs={**instr.attrs, "layer": "ternary_1_5"},
                    type_=TERNARY,
                    metadata=instr.metadata,
                )
                new_instrs.append(ternary_instr)

                # Insert TERNARY_DECODE to get float result back
                if instr.result and ternary_result:
                    dec_instr = Instruction(
                        op=Opcode.TERNARY_DECODE,
                        result=instr.result,
                        operands=[ternary_result],
                        attrs={},
                        type_=FP32,
                    )
                    new_instrs.append(dec_instr)
                    fn.values._table[instr.result] = FP32

            elif instr.op in _ANALOG_OPS:
                # Annotate with MZI parameters
                if "weight" in instr.attrs:
                    instr.attrs["mzi_phase_rad"] = mzi_phase_for_weight(
                        float(instr.attrs["weight"])
                    )
                instr.attrs["layer"] = "analog_6_7"
                new_instrs.append(instr)

            else:
                new_instrs.append(instr)

        bb.instructions = new_instrs

"""
Topology Fingerprint
=====================
Generates a **mathematically unique, deterministic hash** of the LightRail
20-layer photonic fabric's current physical topology and link-utilisation
state.

The fingerprint serves three purposes:

  1. **Route caching** — identical topology + workload → identical optimal
     route, so we cache and replay without re-solving.

  2. **Congestion detection** — successive fingerprints are compared to
     identify which links are accumulating utilisation so the Topology-Aware
     Router can pre-emptively re-route before the electrical I/O wall is hit.

  3. **Provability** — every routing decision is stamped with the fingerprint
     of the topology it was solved against, making the entire compilation
     chain auditable and reproducible.

Structure of a TopologyFingerprint:
  - 20-element layer-utilisation vector (float64, one per fabric layer)
  - 20×64 channel occupancy matrix  (bool, layer × WDM channel)
  - 20×20 inter-layer latency matrix (float64, nanoseconds)
  - SHA-256 digest of the above     (32 bytes → 64 hex chars)
"""

from __future__ import annotations
import hashlib
import struct
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


FABRIC_LAYERS   = 20
WDM_CHANNELS    = 64
HOP_LATENCY_NS  = 0.05   # 50 ps per layer hop


# ---------------------------------------------------------------------------
# Fabric link state
# ---------------------------------------------------------------------------

@dataclass
class LinkState:
    """Instantaneous utilisation of a single fabric link."""
    layer:        int
    channel:      int
    utilisation:  float   # 0.0 – 1.0
    latency_ns:   float   # current measured latency
    congested:    bool    = False

    def __post_init__(self) -> None:
        self.congested = self.utilisation > 0.85


@dataclass
class FabricTopologyState:
    """
    Complete snapshot of the 20-layer × 64-channel photonic fabric.

    In production this would be populated by the Fabric OS telemetry daemon.
    In simulation it is initialised to a clean (zero-utilisation) state.
    """
    layers:          int = FABRIC_LAYERS
    channels:        int = WDM_CHANNELS
    timestamp_ns:    float = field(default_factory=lambda: time.perf_counter_ns())

    # layer × channel utilisation  [0.0, 1.0]
    utilisation:     List[List[float]] = field(
        default_factory=lambda: [[0.0] * WDM_CHANNELS for _ in range(FABRIC_LAYERS)]
    )

    # inter-layer hop latencies (nanoseconds)
    hop_latency:     List[List[float]] = field(
        default_factory=lambda: [
            [HOP_LATENCY_NS if abs(i - j) == 1 else 0.0
             for j in range(FABRIC_LAYERS)]
            for i in range(FABRIC_LAYERS)
        ]
    )

    # per-layer bandwidth remaining (Gb/s)
    remaining_bw_gbps: List[float] = field(
        default_factory=lambda: [3200.0] * FABRIC_LAYERS
    )

    def mark_used(self, layer: int, channel: int, load: float = 0.1) -> None:
        """Record additional load on a link (call after routing a flow)."""
        self.utilisation[layer][channel] = min(
            1.0, self.utilisation[layer][channel] + load
        )

    def congested_links(self) -> List[Tuple[int, int]]:
        """Return (layer, channel) pairs where utilisation > 85 %."""
        return [
            (l, c)
            for l in range(self.layers)
            for c in range(self.channels)
            if self.utilisation[l][c] > 0.85
        ]

    def layer_utilisation(self, layer: int) -> float:
        """Mean utilisation across all channels on a given layer."""
        row = self.utilisation[layer]
        return sum(row) / len(row) if row else 0.0


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------

@dataclass
class TopologyFingerprint:
    """
    Immutable, hashable snapshot of a fabric state.

    digest  : 64-char hex SHA-256 — used as cache key
    state   : the FabricTopologyState at fingerprint time
    version : fingerprint schema version (for forward compatibility)
    """
    digest:    str
    state:     FabricTopologyState
    version:   int = 1
    created_ns: float = field(default_factory=time.perf_counter_ns)

    # ---- factories --------------------------------------------------------

    @classmethod
    def from_state(cls, state: FabricTopologyState) -> "TopologyFingerprint":
        """Compute and return a fingerprint for the given topology state."""
        raw = cls._serialise(state)
        digest = hashlib.sha256(raw).hexdigest()
        return cls(digest=digest, state=state)

    @classmethod
    def clean(cls) -> "TopologyFingerprint":
        """Return a fingerprint for a pristine, zero-utilisation fabric."""
        return cls.from_state(FabricTopologyState())

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _serialise(state: FabricTopologyState) -> bytes:
        """Canonical byte serialisation used for hashing."""
        parts: List[bytes] = []

        # Layer utilisation vector (20 × float64)
        for layer in range(state.layers):
            parts.append(struct.pack(">d", state.layer_utilisation(layer)))

        # Channel occupancy matrix (20 × 64 × float32)
        for layer in range(state.layers):
            for ch in range(state.channels):
                parts.append(struct.pack(">f", state.utilisation[layer][ch]))

        # Inter-layer latency matrix (20 × 20 × float64)
        for i in range(state.layers):
            for j in range(state.layers):
                parts.append(struct.pack(">d", state.hop_latency[i][j]))

        # Remaining bandwidth (20 × float64)
        for bw in state.remaining_bw_gbps:
            parts.append(struct.pack(">d", bw))

        return b"".join(parts)

    def is_clean(self) -> bool:
        """True if all links are at zero utilisation."""
        for row in self.state.utilisation:
            if any(u > 0 for u in row):
                return False
        return True

    def congestion_score(self) -> float:
        """Normalised congestion score [0.0, 1.0] across the entire fabric."""
        total = 0.0
        n = self.state.layers * self.state.channels
        for row in self.state.utilisation:
            total += sum(row)
        return total / n if n else 0.0

    def delta(self, other: "TopologyFingerprint") -> float:
        """L1 distance between two topology states (congestion drift metric)."""
        total = 0.0
        for l in range(self.state.layers):
            for c in range(self.state.channels):
                total += abs(
                    self.state.utilisation[l][c] -
                    other.state.utilisation[l][c]
                )
        return total

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TopologyFingerprint) and self.digest == other.digest

    def __hash__(self) -> int:
        return hash(self.digest)

    def __repr__(self) -> str:
        return (
            f"TopologyFingerprint(digest={self.digest[:12]}..., "
            f"congestion={self.congestion_score():.3f})"
        )


# ---------------------------------------------------------------------------
# Fingerprint cache
# ---------------------------------------------------------------------------

class FingerprintCache:
    """
    LRU-like cache keyed by topology fingerprint digest.
    Used by the TopologyAwareRouter to reuse previously computed optimal routes.
    """

    def __init__(self, max_size: int = 256) -> None:
        self._store:    Dict[str, object] = {}
        self._order:    List[str]         = []
        self.max_size = max_size
        self.hits   = 0
        self.misses = 0

    def get(self, fingerprint: TopologyFingerprint) -> Optional[object]:
        key = fingerprint.digest
        if key in self._store:
            self.hits += 1
            return self._store[key]
        self.misses += 1
        return None

    def put(self, fingerprint: TopologyFingerprint, value: object) -> None:
        key = fingerprint.digest
        if key not in self._store:
            if len(self._order) >= self.max_size:
                oldest = self._order.pop(0)
                del self._store[oldest]
            self._order.append(key)
        self._store[key] = value

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def stats(self) -> Dict[str, object]:
        return {
            "size":     len(self._store),
            "hits":     self.hits,
            "misses":   self.misses,
            "hit_rate": f"{self.hit_rate():.1%}",
        }

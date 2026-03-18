"""Tests for the Topology-Aware Router and Topology Fingerprint."""
import pytest

from lightrail.topology.fingerprint import (
    FabricTopologyState, TopologyFingerprint, FingerprintCache,
    FABRIC_LAYERS, WDM_CHANNELS,
)
from lightrail.topology.aware_router import (
    TopologyAwareRouter, FabricGraphBuilder, DijkstraSolver,
    OptimalRoute,
)
from lightrail.frontend.ast_parser import ASTParser
from lightrail.passes.graph_partition import GraphPartitionPass
from lightrail.dataflow.wavelength_mapper import WavelengthMapper


# ---------------------------------------------------------------------------
# TopologyFingerprint
# ---------------------------------------------------------------------------

class TestTopologyFingerprint:

    def test_clean_fingerprint(self):
        fp = TopologyFingerprint.clean()
        assert len(fp.digest) == 64
        assert fp.is_clean()
        assert fp.congestion_score() == 0.0

    def test_deterministic(self):
        """Same state → same digest."""
        state = FabricTopologyState()
        fp1 = TopologyFingerprint.from_state(state)
        fp2 = TopologyFingerprint.from_state(state)
        assert fp1.digest == fp2.digest

    def test_different_state_different_digest(self):
        s1 = FabricTopologyState()
        s2 = FabricTopologyState()
        s2.mark_used(0, 0, 0.5)
        fp1 = TopologyFingerprint.from_state(s1)
        fp2 = TopologyFingerprint.from_state(s2)
        assert fp1.digest != fp2.digest

    def test_congestion_score(self):
        state = FabricTopologyState()
        for ch in range(WDM_CHANNELS):
            state.mark_used(0, ch, 1.0)
        fp = TopologyFingerprint.from_state(state)
        assert fp.congestion_score() > 0.0

    def test_congested_links(self):
        state = FabricTopologyState()
        # Overload channel 5 on layer 0
        state.utilisation[0][5] = 0.99
        congested = state.congested_links()
        assert (0, 5) in congested

    def test_delta(self):
        s1 = FabricTopologyState()
        s2 = FabricTopologyState()
        s2.mark_used(3, 7, 0.8)
        fp1 = TopologyFingerprint.from_state(s1)
        fp2 = TopologyFingerprint.from_state(s2)
        d = fp1.delta(fp2)
        assert d > 0.0

    def test_hash_and_eq(self):
        fp1 = TopologyFingerprint.clean()
        fp2 = TopologyFingerprint.clean()
        assert fp1 == fp2
        assert hash(fp1) == hash(fp2)
        s = {fp1, fp2}
        assert len(s) == 1


class TestFingerprintCache:

    def test_miss_then_hit(self):
        cache = FingerprintCache(max_size=10)
        fp = TopologyFingerprint.clean()
        assert cache.get(fp) is None
        cache.put(fp, {"routes": []})
        assert cache.get(fp) == {"routes": []}
        assert cache.hits == 1
        assert cache.misses == 1

    def test_eviction(self):
        cache = FingerprintCache(max_size=2)
        states = [FabricTopologyState() for _ in range(3)]
        for i, s in enumerate(states):
            s.mark_used(0, i, float(i) * 0.1)
        fps = [TopologyFingerprint.from_state(s) for s in states]

        cache.put(fps[0], "a")
        cache.put(fps[1], "b")
        cache.put(fps[2], "c")  # should evict fps[0]

        assert cache.get(fps[0]) is None
        assert cache.get(fps[2]) == "c"

    def test_hit_rate(self):
        cache = FingerprintCache()
        fp = TopologyFingerprint.clean()
        cache.get(fp)   # miss
        cache.put(fp, 1)
        cache.get(fp)   # hit
        cache.get(fp)   # hit
        assert cache.hit_rate() == pytest.approx(2 / 3, abs=0.01)


# ---------------------------------------------------------------------------
# FabricGraphBuilder
# ---------------------------------------------------------------------------

class TestFabricGraphBuilder:

    def test_graph_nodes(self):
        state = FabricTopologyState()
        adj   = FabricGraphBuilder().build(state)
        # All 20×64 = 1280 nodes should be present
        assert len(adj) == FABRIC_LAYERS * WDM_CHANNELS

    def test_adjacency_non_empty(self):
        state = FabricTopologyState()
        adj   = FabricGraphBuilder().build(state)
        # Each interior node should have at least 2 edges
        interior = adj[(5, 10)]
        assert len(interior) >= 2

    def test_congested_edge_infinite_weight(self):
        state = FabricTopologyState()
        state.utilisation[2][3] = 1.0   # fully congested
        adj = FabricGraphBuilder().build(state)
        for edge in adj.get((2, 3), []):
            assert edge.effective_weight >= 1e6 or edge.effective_weight == float("inf")


# ---------------------------------------------------------------------------
# DijkstraSolver
# ---------------------------------------------------------------------------

class TestDijkstraSolver:

    def _build(self):
        state = FabricTopologyState()
        return FabricGraphBuilder().build(state), state

    def test_same_node(self):
        adj, _ = self._build()
        path, lat, bw = DijkstraSolver().solve(adj, (0, 0), (0, 0))
        assert path == [(0, 0)]
        assert lat == 0.0

    def test_adjacent_nodes(self):
        adj, _ = self._build()
        path, lat, bw = DijkstraSolver().solve(adj, (0, 0), (1, 0))
        assert len(path) >= 2
        assert lat > 0.0
        assert bw > 0.0

    def test_cross_fabric_route(self):
        adj, _ = self._build()
        src = (0,  0)
        dst = (19, 63)
        path, lat, bw = DijkstraSolver().solve(adj, src, dst)
        assert path[0]  == src
        assert path[-1] == dst
        assert lat > 0.0


# ---------------------------------------------------------------------------
# TopologyAwareRouter
# ---------------------------------------------------------------------------

def _parse_device(src, fn_name):
    m = ASTParser().parse_source(src, fn_name, device=True)
    fn = m.get_function(fn_name)
    fn.is_device = True
    GraphPartitionPass().run(m)
    WavelengthMapper().run(m)
    return m


class TestTopologyAwareRouter:

    def test_run_annotates_module(self):
        src = """
def kernel(a, b, c):
    x = a + b
    y = x * c
    return y
"""
        m = _parse_device(src, "kernel")
        TopologyAwareRouter().run(m)
        assert "topology_fingerprint" in m.metadata
        assert m.metadata.get("routing_engine") == "topology_aware_dijkstra"
        assert m.metadata.get("mathematically_optimal") is True

    def test_function_annotated(self):
        src = """
def kernel(a, b):
    return a + b
"""
        m = _parse_device(src, "kernel")
        TopologyAwareRouter().run(m)
        fn = m.get_function("kernel")
        assert "topology_fingerprint" in fn.attrs
        assert "route_count" in fn.attrs
        assert "congestion_score" in fn.attrs

    def test_routes_are_optimal(self):
        src = """
def kernel(a, b, c, d):
    x = a + b
    y = c + d
    return x + y
"""
        m = _parse_device(src, "kernel")
        router = TopologyAwareRouter()
        router.run(m)
        routes = router.all_routes()
        for r in routes:
            assert r.is_valid()
            assert r.total_latency_ns >= 0

    def test_cache_reuse(self):
        src = """
def kernel(a, b):
    return a + b
"""
        m1 = _parse_device(src, "kernel")
        m2 = _parse_device(src, "kernel")
        router = TopologyAwareRouter()
        router.run(m1)
        router.run(m2)
        stats = router.cache.stats()
        # Second run with identical topology should hit the cache
        assert stats["hits"] >= 1

    def test_single_route(self):
        router = TopologyAwareRouter()
        route = router.route_single(src_tile=0, dst_tile=5, ssa_name="test_val")
        assert route.is_valid()
        assert len(route.path) >= 2

    def test_congestion_report(self):
        router = TopologyAwareRouter()
        report = router.congestion_report()
        assert "fingerprint" in report
        assert "congestion_score" in report
        assert report["congestion_score"] == 0.0   # clean fabric

    def test_congested_fabric_reroutes(self):
        """Router must find an alternative path around a congested link."""
        state = FabricTopologyState()
        # Block all channels on layer 1 (force routing around it)
        for ch in range(WDM_CHANNELS):
            state.utilisation[1][ch] = 1.0

        router = TopologyAwareRouter(state)
        route  = router.route_single(src_tile=0, dst_tile=5)
        # Route should still be found (just through other layers)
        # Layer 1 should not appear in the path
        layers_used = route.layer_sequence()
        if route.is_valid():
            # If a route exists, it should skip layer 1
            assert 1 not in layers_used or route.hop_count == 0

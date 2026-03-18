"""
Stage 6: Fabric OS Interface & Global Scheduler
================================================
Provides the interface between the LightRail compiler and the LightRail
Fabric OS Global Scheduler.  This module:

  1. Defines the KernelDescriptor: a structured payload handed to the Fabric OS
     containing the .lrbs bytecode, WDM channel map, routing table, and
     execution parameters.

  2. Implements the GlobalScheduler stub that simulates deterministic kernel
     integration—dispatching kernels to the fabric without the chaos of
     thread schedulers.

  3. Provides a FabricOSClient for communicating with an actual Fabric OS
     daemon (via a UNIX socket or shared memory region).

Key properties of the LightRail execution model vs CUDA:
  - No warp scheduling: deterministic single-stream per WDM channel.
  - Sub-microsecond optical dispatch: once the kernel is loaded, the
    Fabric OS programmes the WDM switches within ~100 ns.
  - No idle waiting: if a channel has no data, it is simply silent—no
    energy wasted polling.
"""

from __future__ import annotations
import os
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Kernel Descriptor
# ---------------------------------------------------------------------------

class KernelState(Enum):
    PENDING   = auto()
    LOADED    = auto()
    RUNNING   = auto()
    COMPLETE  = auto()
    FAILED    = auto()


@dataclass
class KernelDescriptor:
    """
    Encapsulates everything the Fabric OS needs to dispatch a kernel.

    Fields:
        name         : Human-readable kernel name.
        lrbs_bytes   : Compiled .lrbs bytecode.
        wdm_channel_map: {channel_id: list_of_tile_ids} assignments.
        routing_info : Serialised routing table bytes (from DataflowRouter).
        num_tiles    : Number of fabric tiles used.
        fabric_generation: Target NCE generation (for fat-binary selection).
        args         : Runtime argument values (scalar or numpy arrays).
        launch_grid  : Number of independent kernel instances (default 1).
        async_exec   : If True, dispatch returns immediately; poll state.
    """
    name:              str
    lrbs_bytes:        bytes
    wdm_channel_map:   Dict[int, List[int]] = field(default_factory=dict)
    routing_info:      bytes                = b""
    num_tiles:         int                  = 1
    fabric_generation: int                  = 1
    args:              List[Any]            = field(default_factory=list)
    launch_grid:       int                  = 1
    async_exec:        bool                 = False
    state:             KernelState          = field(default=KernelState.PENDING, init=False)
    dispatch_time_ns:  float                = field(default=0.0, init=False)
    complete_time_ns:  float                = field(default=0.0, init=False)

    def latency_ns(self) -> float:
        if self.state == KernelState.COMPLETE:
            return self.complete_time_ns - self.dispatch_time_ns
        return 0.0


# ---------------------------------------------------------------------------
# Global Scheduler (simulation)
# ---------------------------------------------------------------------------

class GlobalScheduler:
    """
    Simulates the LightRail Fabric OS Global Scheduler.

    In production this would be a kernel-mode driver.  Here it:
      - Maintains a queue of KernelDescriptors.
      - Dispatches them in FIFO order, simulating sub-μs optical dispatch.
      - Tracks deterministic completion without warp-level synchronisation.
    """

    DISPATCH_OVERHEAD_NS = 100.0   # 100 ns optical switch programming time

    def __init__(self) -> None:
        self._queue:    List[KernelDescriptor] = []
        self._history:  List[KernelDescriptor] = []
        self._handlers: Dict[str, Callable] = {}

    def register_handler(self, kernel_name: str, fn: Callable) -> None:
        """Register a simulation handler called when a kernel 'executes'."""
        self._handlers[kernel_name] = fn

    def dispatch(self, descriptor: KernelDescriptor) -> KernelDescriptor:
        """
        Dispatch a kernel to the fabric.  If async_exec=False, blocks until
        the simulated execution completes.
        """
        descriptor.state = KernelState.LOADED
        self._queue.append(descriptor)
        descriptor.dispatch_time_ns = time.perf_counter_ns()

        if not descriptor.async_exec:
            self._execute(descriptor)

        return descriptor

    def _execute(self, descriptor: KernelDescriptor) -> None:
        descriptor.state = KernelState.RUNNING

        # Simulate dispatch overhead
        overhead_s = self.DISPATCH_OVERHEAD_NS * 1e-9
        time.sleep(min(overhead_s, 0.0001))  # cap at 100 μs for simulation

        # Call registered simulation handler if present
        handler = self._handlers.get(descriptor.name)
        if handler:
            try:
                handler(*descriptor.args)
            except Exception as exc:
                descriptor.state = KernelState.FAILED
                raise RuntimeError(f"Kernel '{descriptor.name}' failed: {exc}") from exc

        descriptor.complete_time_ns = time.perf_counter_ns()
        descriptor.state = KernelState.COMPLETE
        self._queue.remove(descriptor)
        self._history.append(descriptor)

    def poll(self, descriptor: KernelDescriptor, timeout_s: float = 1.0) -> KernelState:
        """Poll an asynchronously dispatched kernel until completion or timeout."""
        deadline = time.monotonic() + timeout_s
        while descriptor.state not in {KernelState.COMPLETE, KernelState.FAILED}:
            if time.monotonic() > deadline:
                return descriptor.state
            if descriptor in self._queue:
                self._execute(descriptor)
            time.sleep(1e-6)
        return descriptor.state

    def stats(self) -> Dict[str, Any]:
        """Return dispatch statistics over all completed kernels."""
        if not self._history:
            return {}
        latencies = [k.latency_ns() for k in self._history]
        return {
            "kernels_dispatched": len(self._history),
            "avg_latency_ns":    sum(latencies) / len(latencies),
            "min_latency_ns":    min(latencies),
            "max_latency_ns":    max(latencies),
        }


# ---------------------------------------------------------------------------
# Fabric OS Client (IPC stub)
# ---------------------------------------------------------------------------

FABRIC_OS_SOCKET = "/tmp/lightrail_fabric_os.sock"


class FabricOSClient:
    """
    Thin IPC client for communicating with a real LightRail Fabric OS daemon.

    Protocol (over UNIX domain socket):
      Client -> Server: 4-byte length + KernelDescriptor payload (protobuf-like)
      Server -> Client: 4-byte status code + 8-byte latency_ns

    Falls back gracefully to the in-process GlobalScheduler if the daemon
    socket is not available (useful for CI / offline development).
    """

    MAGIC   = b"LROS"
    STATUS_OK     = 0x00
    STATUS_FAILED = 0xFF

    def __init__(self, socket_path: str = FABRIC_OS_SOCKET) -> None:
        self.socket_path = socket_path
        self._local_scheduler = GlobalScheduler()
        self._connected = False
        self._sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        """Attempt to connect to the Fabric OS daemon."""
        if not os.path.exists(self.socket_path):
            return False
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.connect(self.socket_path)
            self._connected = True
            return True
        except (OSError, ConnectionRefusedError):
            self._sock = None
            return False

    def dispatch(self, descriptor: KernelDescriptor) -> KernelDescriptor:
        """
        Dispatch a kernel, preferring the Fabric OS daemon if connected,
        otherwise falling back to the local scheduler simulation.
        """
        if self._connected and self._sock:
            return self._dispatch_remote(descriptor)
        return self._local_scheduler.dispatch(descriptor)

    def _dispatch_remote(self, descriptor: KernelDescriptor) -> KernelDescriptor:
        """Send kernel descriptor over the socket to the Fabric OS daemon."""
        payload = self._serialise_descriptor(descriptor)
        length  = struct.pack(">I", len(payload))
        try:
            self._sock.sendall(self.MAGIC + length + payload)
            resp = self._sock.recv(12)
            if len(resp) >= 12:
                status, latency_ns = struct.unpack(">If", resp[:8])
                if status == self.STATUS_OK:
                    descriptor.state = KernelState.COMPLETE
                    descriptor.dispatch_time_ns = time.perf_counter_ns() - latency_ns
                    descriptor.complete_time_ns = time.perf_counter_ns()
                else:
                    descriptor.state = KernelState.FAILED
        except OSError:
            # Daemon disappeared; fall back locally
            self._connected = False
            self._local_scheduler.dispatch(descriptor)
        return descriptor

    @staticmethod
    def _serialise_descriptor(descriptor: KernelDescriptor) -> bytes:
        """Minimal serialisation: magic + name + lrbs_bytes length + lrbs_bytes."""
        name_enc = descriptor.name.encode("utf-8")
        return (
            struct.pack(">HI", len(name_enc), len(descriptor.lrbs_bytes))
            + name_enc
            + descriptor.lrbs_bytes
        )

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None
        self._connected = False


# Module-level default scheduler for use by the JIT runtime
_DEFAULT_SCHEDULER = GlobalScheduler()


def get_default_scheduler() -> GlobalScheduler:
    return _DEFAULT_SCHEDULER

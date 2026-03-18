"""
Stage 5: Fat Binary Bundler
============================
Combines:
  - Standard CPU host code (Python callable or C++ object)
  - One or more versions of LightRail device bytecode (.lrbs blobs)

into a single portable .lrfat (LightRail Fat Binary) archive.

The Fat Binary format mirrors the approach used by NVIDIA's CUDA fat binaries
but targets LightRail fabric generations:

    .lrfat archive layout:
    ┌──────────────────────────────────────────────────────────┐
    │ LRFAT_MAGIC (4) + VERSION (2) + FLAGS (2)                │
    │ MANIFEST (JSON-encoded descriptor)                       │
    │ SECTION: host_code   (CPU Python/C++ bytecode)           │
    │ SECTION: lrbs_gen1   (.lrbs for NCE Generation 1)        │
    │ SECTION: lrbs_gen2   (.lrbs for NCE Generation 2)        │
    │ ...                                                      │
    │ CHECKSUM (CRC32)                                         │
    └──────────────────────────────────────────────────────────┘

At runtime, the LightRail driver selects the best matching .lrbs blob for
the detected hardware generation, or falls back to JIT compilation if none
matches.
"""

from __future__ import annotations
import json
import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional


LRFAT_MAGIC   = b"LRFT"
LRFAT_VERSION = (0, 1)


@dataclass
class FatBinarySection:
    """One section of the fat binary."""
    tag:     str     # e.g., "host_code", "lrbs_gen1"
    data:    bytes
    attrs:   Dict[str, str] = field(default_factory=dict)

    def header(self) -> bytes:
        tag_enc   = self.tag.encode("utf-8")
        attrs_enc = json.dumps(self.attrs).encode("utf-8")
        return struct.pack(">HHI", len(tag_enc), len(attrs_enc), len(self.data))

    def serialise(self) -> bytes:
        tag_enc   = self.tag.encode("utf-8")
        attrs_enc = json.dumps(self.attrs).encode("utf-8")
        hdr = struct.pack(">HHI", len(tag_enc), len(attrs_enc), len(self.data))
        return hdr + tag_enc + attrs_enc + self.data


@dataclass
class FatBinary:
    """
    In-memory representation of an .lrfat archive.
    Sections are ordered: host first, then device blobs by generation.
    """
    name:     str
    sections: List[FatBinarySection] = field(default_factory=list)
    manifest: Dict[str, object] = field(default_factory=dict)

    def add_host(self, data: bytes, attrs: Optional[Dict[str, str]] = None) -> None:
        self.sections.append(FatBinarySection("host_code", data, attrs or {}))

    def add_device(self, generation: int, data: bytes,
                   attrs: Optional[Dict[str, str]] = None) -> None:
        tag = f"lrbs_gen{generation}"
        self.sections.append(FatBinarySection(tag, data, attrs or {}))

    def serialise(self) -> bytes:
        parts = []
        parts.append(LRFAT_MAGIC)
        parts.append(struct.pack(">BBH", LRFAT_VERSION[0], LRFAT_VERSION[1], 0))

        # Manifest
        self.manifest["name"]          = self.name
        self.manifest["section_count"] = len(self.sections)
        self.manifest["sections"]      = [s.tag for s in self.sections]
        manifest_bytes = json.dumps(self.manifest, indent=2).encode("utf-8")
        parts.append(struct.pack(">I", len(manifest_bytes)))
        parts.append(manifest_bytes)

        # Sections
        for sec in self.sections:
            parts.append(sec.serialise())

        payload = b"".join(parts)
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        return payload + struct.pack(">I", crc)

    @classmethod
    def deserialise(cls, data: bytes) -> "FatBinary":
        """Parse a serialised .lrfat byte string back into a FatBinary object."""
        offset = 0

        def read(n: int) -> bytes:
            nonlocal offset
            chunk = data[offset:offset + n]
            offset += n
            return chunk

        magic = read(4)
        assert magic == LRFAT_MAGIC, f"Bad magic: {magic!r}"
        _major, _minor, _flags = struct.unpack(">BBH", read(4))

        (manifest_len,) = struct.unpack(">I", read(4))
        manifest = json.loads(read(manifest_len))

        fb = cls(name=manifest.get("name", "unknown"))
        fb.manifest = manifest

        n_sections = manifest.get("section_count", 0)
        for _ in range(n_sections):
            tag_len, attrs_len, data_len = struct.unpack(">HHI", read(8))
            tag   = read(tag_len).decode("utf-8")
            attrs = json.loads(read(attrs_len))
            sec_data = read(data_len)
            fb.sections.append(FatBinarySection(tag=tag, data=sec_data, attrs=attrs))

        return fb


class FatBinaryBundler:
    """
    Bundles host code and one or more device .lrbs blobs into a .lrfat file.
    """

    def bundle(
        self,
        name: str,
        host_bytes: bytes,
        device_blobs: Dict[int, bytes],  # {generation: lrbs_bytes}
        manifest_extra: Optional[Dict[str, object]] = None,
    ) -> bytes:
        """
        Args:
            name          : Application / module name.
            host_bytes    : Serialised host code (pickled callable, etc.).
            device_blobs  : Mapping from fabric generation (int) to .lrbs bytes.
            manifest_extra: Optional extra metadata added to the manifest.

        Returns:
            Serialised .lrfat bytes.
        """
        fb = FatBinary(name=name)
        if manifest_extra:
            fb.manifest.update(manifest_extra)

        fb.add_host(
            host_bytes,
            attrs={"lang": "python", "abi": "lightrail-0.1"},
        )
        for gen, blob in sorted(device_blobs.items()):
            fb.add_device(
                gen,
                blob,
                attrs={"nce_generation": str(gen), "isa": "lrbs-0.1"},
            )

        return fb.serialise()

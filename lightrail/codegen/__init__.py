"""LightRail Stage 5: Bytecode & Fat Binary Generation."""
from lightrail.codegen.bytecode   import BytecodeEmitter, LRBSFile, LRBS_FLAGS_AOT, LRBS_FLAGS_JIT
from lightrail.codegen.fat_binary import FatBinaryBundler, FatBinary, FatBinarySection
from lightrail.codegen.ternary    import TernaryEncodingPass

__all__ = [
    "BytecodeEmitter", "LRBSFile", "LRBS_FLAGS_AOT", "LRBS_FLAGS_JIT",
    "FatBinaryBundler", "FatBinary", "FatBinarySection",
    "TernaryEncodingPass",
]

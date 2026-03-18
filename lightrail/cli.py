"""
LightRail Compiler CLI (lrc)
==============================
Command-line interface for compiling Python source files through the
LightRail photonic compiler pipeline.

Usage:
    lrc compile path/to/kernel.py --fn dot_product --mode jit
    lrc compile path/to/kernel.py --fn matmul --mode aot -o matmul.lrnpu
    lrc inspect matmul.lrbs
    lrc ir path/to/kernel.py --fn dot_product
"""

from __future__ import annotations
import sys
import os

try:
    import click
except ImportError:
    click = None  # type: ignore


def _require_click():
    if click is None:
        print("ERROR: 'click' is required for the CLI. Install with: pip install click")
        sys.exit(1)


def main():
    _require_click()
    cli()


if click is not None:
    @click.group()
    @click.version_option(version="0.1.0", prog_name="lrc")
    def cli():
        """LightRail Compiler (lrc) — compile Python/C++ for the LightRail NCE."""
        pass

    @cli.command()
    @click.argument("source_file", type=click.Path(exists=True))
    @click.option("--fn",    "-f", required=True, help="Function name to compile")
    @click.option("--mode",  "-m", default="jit",
                  type=click.Choice(["jit", "aot"]), show_default=True)
    @click.option("--out",   "-o", default=None, help="Output file path")
    @click.option("--channels", default=64, show_default=True,
                  help="Number of WDM channels (1-64)")
    @click.option("--gen",   default=1, show_default=True,
                  help="NCE hardware generation")
    @click.option("--no-fma",    is_flag=True, help="Disable FMA fusion")
    @click.option("--no-ternary",is_flag=True, help="Disable ternary encoding")
    @click.option("--debug", is_flag=True,     help="Include debug info")
    def compile(source_file, fn, mode, out, channels, gen, no_fma, no_ternary, debug):
        """Compile a Python function for the LightRail NCE."""
        from lightrail.pipeline import CompilationPipeline, CompileOptions

        with open(source_file) as f:
            source = f.read()

        opts = CompileOptions(
            mode=mode,
            num_wdm_channels=channels,
            nce_generation=gen,
            enable_fma=not no_fma,
            enable_ternary=not no_ternary,
            debug=debug,
        )
        pipeline = CompilationPipeline(opts)

        click.echo(f"Compiling '{fn}' from {source_file} ...")
        result = pipeline.compile_source(source, fn, device=True)
        click.echo(result.summary())

        # Write output
        if out is None:
            base = os.path.splitext(source_file)[0]
            out  = f"{base}.lrnpu" if mode == "aot" else f"{base}.lrbs"

        if mode == "aot" and result.aot_binary:
            data = result.aot_binary.serialise()
        else:
            data = result.lrbs_bytes

        with open(out, "wb") as f:
            f.write(data)

        click.echo(f"Output written to: {out} ({len(data)} bytes)")

    @cli.command()
    @click.argument("source_file", type=click.Path(exists=True))
    @click.option("--fn", "-f", required=True, help="Function name")
    @click.option("--channels", default=64, show_default=True)
    def ir(source_file, fn, channels):
        """Dump the compiled IR for a function."""
        from lightrail.pipeline import CompilationPipeline, CompileOptions

        with open(source_file) as f:
            source = f.read()

        opts = CompilationPipeline(CompileOptions(num_wdm_channels=channels))
        result = opts.compile_source(source, fn, device=True)
        click.echo(result.module.dump())

    @cli.command()
    @click.argument("binary_file", type=click.Path(exists=True))
    def inspect(binary_file):
        """Inspect a .lrbs or .lrfat binary file."""
        with open(binary_file, "rb") as f:
            data = f.read()

        magic = data[:4]
        click.echo(f"File: {binary_file} ({len(data)} bytes)")
        click.echo(f"Magic: {magic!r}")

        if magic == b"LRBS":
            major, minor, flags = data[4], data[5], int.from_bytes(data[6:8], "big")
            click.echo(f"Format: LRBS v{major}.{minor}  flags=0x{flags:04x}")
        elif magic == b"LRFT":
            from lightrail.codegen.fat_binary import FatBinary
            fb = FatBinary.deserialise(data)
            click.echo(f"Format: LightRail Fat Binary")
            click.echo(f"Name: {fb.name}")
            click.echo(f"Sections ({len(fb.sections)}):")
            for sec in fb.sections:
                click.echo(f"  [{sec.tag}] {len(sec.data)} bytes  attrs={sec.attrs}")
        elif magic == b"LNPU":
            major, minor, nce_gen = data[4], data[5], int.from_bytes(data[6:8], "big")
            click.echo(f"Format: LightRail NPU Binary v{major}.{minor}  gen={nce_gen}")
        else:
            click.echo(f"Unknown format (magic={magic!r})")

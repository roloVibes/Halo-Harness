"""tests.test_clipboard_image -- Halo 2.0.3.1 (clipboard image paste):
halo_harness/tui/clipboard_image.py's `read_clipboard_image`, hermetic via
the `backend`/`run`/`platform` seams (no real clipboard, no subprocess, no
network) -- the reader's own bytes-in/ClipboardImage-out contract, the 5 MB
cap, the Pillow-optional downscale, and every per-platform argv table
(construction only, never executed).
"""
from __future__ import annotations

import base64
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY"
    "42YAAAAASUVORK5CYII="
)


def _tmp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="halo-clipimg-"))


# ---------------------------------------------------------------------------
# The backend seam itself.
# ---------------------------------------------------------------------------

@test
def test_backend_png_bytes_become_a_written_file_with_size_and_media_type(ctx: Ctx):
    from halo_harness.tui.clipboard_image import read_clipboard_image
    dest = _tmp_dir()
    img = read_clipboard_image(backend=lambda: _TINY_PNG, dest_dir=dest)
    ctx.check("a ClipboardImage came back", img is not None)
    ctx.check(f"the file was actually written, got {img.path}", img.path.is_file())
    ctx.check(f"dimensions sniffed from the PNG header (no Pillow needed for this), got {(img.width, img.height)}",
              (img.width, img.height) == (1, 1))
    ctx.check(f"media type is image/png, got {img.media_type!r}", img.media_type == "image/png")
    ctx.check(f"bytes count matches the written file, got {img.bytes}", img.bytes == img.path.stat().st_size)


@test
def test_backend_returning_none_is_none(ctx: Ctx):
    from halo_harness.tui.clipboard_image import read_clipboard_image
    ctx.check("no image on the clipboard -> None", read_clipboard_image(backend=lambda: None) is None)


@test
def test_backend_that_raises_is_none_never_propagates(ctx: Ctx):
    from halo_harness.tui.clipboard_image import read_clipboard_image

    def _boom():
        raise RuntimeError("clipboard access denied")

    ctx.check("a raising backend degrades to None, never raises", read_clipboard_image(backend=_boom) is None)


@test
def test_backend_bypasses_every_platform_reader_and_pillow_entirely(ctx: Ctx):
    """The whole point of `backend`: NOTHING else is ever consulted, even
    when it returns None -- a test must never fall through to a real
    subprocess/Pillow call just because the hermetic backend had nothing."""
    import halo_harness.tui.clipboard_image as ci_mod

    def _poison(*a, **kw):
        raise AssertionError("a platform reader ran despite an explicit backend")

    old_win, old_wsl = ci_mod._windows_read_bytes, ci_mod._wsl_read_bytes
    ci_mod._windows_read_bytes = _poison
    ci_mod._wsl_read_bytes = _poison
    try:
        ctx.check("platform readers never ran", ci_mod.read_clipboard_image(backend=lambda: None) is None)
    finally:
        ci_mod._windows_read_bytes, ci_mod._wsl_read_bytes = old_win, old_wsl


# ---------------------------------------------------------------------------
# The 5 MB cap and the Pillow-optional downscale (deliverable 2).
# ---------------------------------------------------------------------------

@test
def test_oversized_bytes_raise_image_too_large(ctx: Ctx):
    from halo_harness.tui.clipboard_image import ImageTooLarge, read_clipboard_image
    # Not a real PNG -- sniff_dimensions returns None for it, so the
    # downscale path never fires and the raw byte-count cap is what bites.
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024)
    try:
        read_clipboard_image(backend=lambda: big, dest_dir=_tmp_dir())
        ctx.check("should have raised ImageTooLarge", False)
    except ImageTooLarge as e:
        ctx.check(f"names the real byte count, got {e.num_bytes}", e.num_bytes == len(big))


@test
def test_downscale_shrinks_an_oversized_image_when_pillow_is_present(ctx: Ctx):
    from PIL import Image
    from halo_harness.tui.clipboard_image import read_clipboard_image
    buf = io.BytesIO()
    Image.new("RGB", (2000, 1000), color=(10, 20, 30)).save(buf, format="PNG")
    data = buf.getvalue()
    img = read_clipboard_image(backend=lambda: data, dest_dir=_tmp_dir())
    ctx.check("an image came back", img is not None)
    ctx.check(f"downscaled to the 1568px soft cap on the long side, got {(img.width, img.height)}",
              img.width == 1568 and img.height == 784)
    ctx.check(f"re-encoded PNG, got {img.media_type!r}", img.media_type == "image/png")
    ctx.check("downscaled bytes are smaller than the original", img.bytes < len(data))


@test
def test_downscale_skipped_without_pillow_bytes_pass_through_unchanged(ctx: Ctx):
    import sys as _sys
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (2000, 1000), color=(10, 20, 30)).save(buf, format="PNG")
    data = buf.getvalue()

    old_pil = _sys.modules.get("PIL")
    old_pil_image = _sys.modules.get("PIL.Image")
    _sys.modules["PIL"] = None  # the standard "simulate ImportError" trick
    _sys.modules.pop("PIL.Image", None)
    try:
        from halo_harness.tui.clipboard_image import read_clipboard_image
        img = read_clipboard_image(backend=lambda: data, dest_dir=_tmp_dir())
        ctx.check("still returns an image (no Pillow is never a hard failure)", img is not None)
        ctx.check(f"bytes pass through UNCHANGED, got {img.bytes} vs original {len(data)}", img.bytes == len(data))
        ctx.check(f"dimensions still sniffed (pure stdlib PNG header read), got {(img.width, img.height)}",
                  (img.width, img.height) == (2000, 1000))
    finally:
        if old_pil is not None:
            _sys.modules["PIL"] = old_pil
        else:
            _sys.modules.pop("PIL", None)
        if old_pil_image is not None:
            _sys.modules["PIL.Image"] = old_pil_image


# ---------------------------------------------------------------------------
# Per-platform command tables -- argv construction only, never executed.
# ---------------------------------------------------------------------------

@test
def test_windows_argv_tables(ctx: Ctx):
    from halo_harness.tui.clipboard_image import windows_fallback_argv, windows_primary_argv
    argv = windows_primary_argv(r"C:\tmp\clip.png")
    ctx.check(f"powershell -NoProfile -Command, got {argv[:3]}", argv[:3] == ["powershell", "-NoProfile", "-Command"])
    ctx.check("Clipboard.GetImage + the target path in the script", "Clipboard]::GetImage()" in argv[3]
              and r"C:\tmp\clip.png" in argv[3])
    ctx.check("ImageFormat.Png is how it's saved", "ImageFormat]::Png" in argv[3])
    fallback = windows_fallback_argv(r"C:\tmp\clip2.png")
    ctx.check(f"fallback uses Get-Clipboard -Format Image, got {fallback[3]!r}",
              "Get-Clipboard -Format Image" in fallback[3])


@test
def test_wsl_argv_tables(ctx: Ctx):
    from halo_harness.tui.clipboard_image import is_wsl, wsl_path_convert_argv, wsl_save_argv
    ctx.check("is_wsl detects the real /proc/version wording", is_wsl("Linux version ... Microsoft ..."))
    ctx.check("is_wsl is False for an ordinary Linux kernel string", not is_wsl("Linux version 6.1.0-generic"))
    argv = wsl_save_argv(r"C:\Windows\Temp\x.png")
    ctx.check(f"powershell.exe (the Windows-side binary), got {argv[0]!r}", argv[0] == "powershell.exe")
    ctx.check("same save script as the Windows primary reader", "Clipboard]::GetImage()" in argv[-1])
    conv = wsl_path_convert_argv(r"C:\Windows\Temp\x.png")
    ctx.check(f"wslpath -u <path>, got {conv}", conv == ["wslpath", "-u", r"C:\Windows\Temp\x.png"])


@test
def test_macos_argv_and_applescript_data_parsing(ctx: Ctx):
    from halo_harness.tui.clipboard_image import macos_fallback_argv, macos_primary_argv, parse_applescript_data
    primary = macos_primary_argv()
    ctx.check(f"osascript -e '...PNGf...', got {primary}",
              primary[0] == "osascript" and primary[1] == "-e" and "PNGf" in primary[2])
    fallback = macos_fallback_argv("/tmp/clip.png")
    ctx.check(f"pngpaste <path>, got {fallback}", fallback == ["pngpaste", "/tmp/clip.png"])
    stdout = f"\xabdata PNGf{_TINY_PNG.hex()}\xbb"
    parsed = parse_applescript_data(stdout)
    ctx.check(f"the hex payload decodes back to the exact PNG bytes, got {len(parsed or b'')} bytes",
              parsed == _TINY_PNG)
    ctx.check("no data literal in the text -> None, never raises", parse_applescript_data("no match here") is None)


@test
def test_linux_argv_table_order(ctx: Ctx):
    from halo_harness.tui.clipboard_image import linux_argv_table
    table = linux_argv_table()
    names = [name for name, _argv in table]
    ctx.check(f"wl-paste, then xclip, then xsel, got {names}", names == ["wl-paste", "xclip", "xsel"])
    by_name = dict(table)
    ctx.check(f"wl-paste asks for image/png, got {by_name['wl-paste']}",
              by_name["wl-paste"] == ["wl-paste", "--type", "image/png"])
    ctx.check(f"xclip asks for the clipboard selection + image/png, got {by_name['xclip']}",
              by_name["xclip"] == ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"])
    ctx.check(f"xsel carries no MIME selector of its own (the brief's own 'last try'), got {by_name['xsel']}",
              by_name["xsel"] == ["xsel", "--clipboard", "--output"])


@test
def test_run_seam_dispatches_through_the_windows_reader_end_to_end(ctx: Ctx):
    """The OTHER half of "no execution": `run` (never a real subprocess.run)
    fully stands in for the Windows dispatch path end to end -- argv is
    built, the fake `run` "writes" the file exactly like a real `.Save(...)`
    call would, and the result comes back as a real ClipboardImage."""
    from halo_harness.tui.clipboard_image import read_clipboard_image

    class _FakeCompleted:
        def __init__(self, stdout):
            self.stdout = stdout

    def _fake_run(argv, **_kw):
        # argv[3] is the PowerShell script; the real one's own $i.Save(...)
        # call names the target path as its first quoted argument.
        script = argv[3]
        target = script.split("Save('", 1)[1].split("'", 1)[0]
        Path(target).write_bytes(_TINY_PNG)
        return _FakeCompleted(stdout="ok")

    img = read_clipboard_image(platform="win32", run=_fake_run, dest_dir=_tmp_dir())
    ctx.check(f"a real ClipboardImage came back through the fake run seam, got {img}", img is not None)
    ctx.check(f"dimensions sniffed correctly, got {(img.width, img.height)}", (img.width, img.height) == (1, 1))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))

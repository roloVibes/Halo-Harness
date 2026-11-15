"""tests.helpers.apple_platform -- 3.6.0.0 R12: the mlx tests ask the platform instead of assuming "this box is
never Apple silicon" (an Apple silicon Mac and the macOS CI runners are). `apple_silicon()` is the real answer;
`pinned(apple)` pins `huggingface_mlx.is_apple_silicon` (every caller looks it up at call time) so the non-Apple
refusal is checked on every host; `no_mlx_runtime()` makes the mlx_lm binary absent so an Apple-silicon run never
starts a server or downloads a model, whatever is installed."""
from __future__ import annotations

from contextlib import contextmanager


def apple_silicon() -> bool:
    from halo_harness.providers.huggingface_mlx import is_apple_silicon
    return is_apple_silicon()


@contextmanager
def pinned(apple: bool):
    from halo_harness.providers import huggingface_mlx as m
    saved = m.is_apple_silicon
    m.is_apple_silicon = lambda **_kw: apple
    try:
        yield
    finally:
        m.is_apple_silicon = saved


@contextmanager
def no_mlx_runtime():
    from halo_harness.providers import local_runtime as lr
    saved = lr.find_runtime_binary
    lr.find_runtime_binary = lambda *_a, **_kw: None
    try:
        yield
    finally:
        lr.find_runtime_binary = saved

"""halo_harness.tools.media -- Halo 2.0.7 round 0e: the ONE deterministic
media-ingestion tool behind the one media agent (rolo: "one media agent,
not three"). Video becomes FRAMES (evenly spaced PNGs, local ffmpeg, no
model involved in the extraction); audio and everything else becomes
ffprobe METADATA plus a whisper hint -- because ingestion is deterministic
tooling, not model choice. The agent that calls this tool (running on a
vision-capable lane, e.g. the concierge/eyes model) then Reads the frames
for actual understanding.

Never transcodes, never uploads, never spends a token on extraction.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from halo_harness.tools.base import Tool, ToolContext, ToolResult

_MAX_FRAMES = 8
_DEFAULT_FRAMES = 4
_PROBE_TIMEOUT_S = 15.0


def _run_json(argv: list) -> Optional[dict]:
    try:
        out = subprocess.run(argv, capture_output=True, text=True,
                             timeout=_PROBE_TIMEOUT_S, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout or "{}")
    except ValueError:
        return None


class MediaTool(Tool):
    name: str = "Media"
    description: str = (
        "Extract evenly-spaced frames and technical metadata from a media file (video/audio) "
        "using local ffmpeg/ffprobe. Returns the media summary and the written frame file paths; "
        "Read the frame images afterward to actually look at them. Extraction is local and "
        "deterministic -- no model is involved in it."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the media file"},
            "frames": {"type": "integer",
                       "description": f"How many evenly-spaced frames to extract from a video "
                                      f"(1-{_MAX_FRAMES}, default {_DEFAULT_FRAMES})"},
        },
        "required": ["path"],
    }
    is_read_only: bool = False   # writes frame PNGs into the session dir
    is_destructive: bool = False
    result_cap: Optional[int] = 4000

    def summary(self, input: dict) -> str:
        p = (input or {}).get("path", "")
        return f"Media({Path(p).name if p else '?'})"

    def permission_content(self, input: dict) -> str:
        return (input or {}).get("path", "") if isinstance(input, dict) else ""

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        path_raw = input.get("path") if isinstance(input, dict) else None
        if not path_raw:
            return ToolResult("The path parameter is required", is_error=True)
        path = Path(path_raw).expanduser()
        if not path.is_file():
            return ToolResult(f"No such file: {path}", is_error=True)
        frames = input.get("frames") if isinstance(input, dict) else None
        if not isinstance(frames, int) or isinstance(frames, bool) or frames < 1:
            frames = _DEFAULT_FRAMES
        frames = min(frames, _MAX_FRAMES)

        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return ToolResult(
                "ffprobe is not on PATH -- install ffmpeg (winget install ffmpeg / "
                "apt install ffmpeg) and retry", is_error=True)

        probe = _run_json([ffprobe, "-v", "quiet", "-print_format", "json",
                           "-show_format", "-show_streams", str(path)])
        if not probe:
            return ToolResult(f"ffprobe could not read {path.name}", is_error=True)

        fmt = probe.get("format") or {}
        streams = probe.get("streams") or []
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        try:
            duration_s = float(fmt.get("duration") or 0.0)
        except (TypeError, ValueError):
            duration_s = 0.0

        lines = [f"{path.name}: {fmt.get('format_long_name') or fmt.get('format_name') or 'media'}"
                 + (f", {duration_s:.1f}s" if duration_s else "")
                 + f", {int(fmt.get('size') or 0) // 1024} KiB"]
        if video_streams:
            v = video_streams[0]
            lines.append(f"video: {v.get('codec_name')} {v.get('width')}x{v.get('height')}"
                         + (f" @ {v.get('avg_frame_rate') or '?'} fps" if v.get("avg_frame_rate") else ""))
        if audio_streams:
            a = audio_streams[0]
            lines.append(f"audio: {a.get('codec_name')} {a.get('sample_rate')} Hz"
                         + (f", {a.get('channels')} ch" if a.get("channels") else ""))

        if not video_streams:
            lines.append("no video stream -- for a transcript, transcribe with whisper via Bash "
                         "(`whisper <file> --model small --output_format txt`) when it is installed")
            return ToolResult("\n".join(lines))

        if not ffmpeg:
            lines.append("ffmpeg is not on PATH -- cannot extract frames (metadata above)")
            return ToolResult("\n".join(lines))

        out_dir = (Path(ctx.session_dir) / "media" / (ctx.tool_use_id or uuid.uuid4().hex[:12]))
        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for i in range(frames):
            t = (duration_s * (i + 0.5)) / frames if duration_s else 0.0
            out = out_dir / f"frame_{i + 1:02d}.png"
            argv = [ffmpeg, "-hide_banner", "-loglevel", "error",
                    "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-y", str(out)]
            try:
                r = subprocess.run(argv, capture_output=True, text=True, timeout=60.0, check=False)
            except (OSError, subprocess.TimeoutExpired) as e:
                lines.append(f"frame {i + 1}: extraction failed ({type(e).__name__})")
                continue
            if r.returncode == 0 and out.exists():
                written.append(out)
            else:
                lines.append(f"frame {i + 1}: ffmpeg failed"
                             + (f": {(r.stderr or '').strip()[:120]}" if r.stderr else ""))

        if not written:
            return ToolResult("\n".join(lines) + "\n(no frames extracted)", is_error=True)
        lines.append(f"{len(written)} frames written:")
        lines.extend(f"  {p}" for p in written)
        lines.append("Read the frame images to look at them (a vision-capable model sees them "
                     "as images; Read works frame by frame).")
        return ToolResult("\n".join(lines))

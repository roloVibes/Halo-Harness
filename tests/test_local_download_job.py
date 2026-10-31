"""tests.test_local_download_job -- Halo 3.3.5.0 R5: studio/local_download_job.py, the pull jobs' machinery with
`kind: "download"`, against the fake hub (tests/helpers/hf_local_env.HfHome: a fresh home, one model folder,
HF_ENDPOINT on 127.0.0.1:0):

1. the frames: `download` events with the pull job's shape (percent, the file as the digest, done, ok), the job in
   GET local/downloads and in GET local/pulls (the Jobs list shows both kinds), not in pulls.json's `pull` set;
2. a second ask for the same folder + repo/file joins the running job; another file is its own job;
3. a cancel: the job says the part file keeps its bytes, the folder lists the part, the next download resumes;
4. the model folder's listing (GET local/hf/dirs) is read again when one lands: the model is there with its card,
   its fit on box and the serve line.
Run: python -m tests.test_local_download_job
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.hf_local_env import GGUF, HfHome  # noqa: E402
from tests.helpers.mock_hub import gguf_bytes  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _start(h, repo=GGUF, file="Tiny-1B-Q4_K_M.gguf", frames=None):
    from halo_harness.studio import local_download_job as DJ
    return DJ.start(h.models, repo, file, (frames.append if frames is not None else None))


@test
def test_frames_and_the_jobs_lists(ctx: Ctx):
    with HfHome() as h:
        frames: list = []
        v = _start(h, frames=frames)
        ctx.check(f"a job of kind download, got {v}", v["kind"] == "download" and not v["joined"] and v["repo"] == GGUF)
        end = h.wait_job(v["job"])
        ctx.check(f"it ends ok at 100 %, the path said, got {end}", end.get("ok") and end.get("percent") == 100.0
                  and str(end.get("path") or "").endswith("Tiny-1B-Q4_K_M.gguf"))
        kinds = {f["event"] for f in frames}
        last = frames[-1]["data"]
        ctx.check(f"`download` frames with the pull shape, got {kinds} {last}", kinds == {"download"} and last["done"]
                  and last["digest"] == "Tiny-1B-Q4_K_M.gguf" and last["kind"] == "download" and last["host"] == str(h.models))
        ctx.check("in local/pulls too (the Jobs list)", any(j["job"] == v["job"] for j in h.api("GET", "local/pulls")[1]["jobs"]))
        from halo_harness.studio import local_pull_job as J
        ctx.check("not in the pull set a member pushes", all(j["kind"] == "pull" for j in J.current("pull")["jobs"]))


@test
def test_a_second_ask_joins(ctx: Ctx):
    with HfHome() as h:
        h.hub.add("example-org/Slow-GGUF", {"Slow-Q4_K_M.gguf": gguf_bytes(2 * 1024 * 1024, "s"), "Slow-Q8_0.gguf": gguf_bytes(70_000, "t")})
        h.hub.delay_s = 0.01
        a = _start(h, "example-org/Slow-GGUF", "Slow-Q4_K_M.gguf")
        b = _start(h, "example-org/Slow-GGUF", "Slow-Q4_K_M.gguf")
        c = _start(h, "example-org/Slow-GGUF", "Slow-Q8_0.gguf")
        ctx.check(f"joined the same job, got {a['job']} {b['job']} {b['joined']}", b["joined"] and b["job"] == a["job"])
        ctx.check("another file is its own job", c["job"] != a["job"] and not c["joined"])
        h.hub.delay_s = 0.0
        ctx.check("both end ok", h.wait_job(a["job"]).get("ok") and h.wait_job(c["job"]).get("ok"))


@test
def test_a_cancel_keeps_the_part_and_the_next_resumes(ctx: Ctx):
    with HfHome() as h:
        h.hub.add("example-org/Big-GGUF", {"Big-Q4_K_M.gguf": gguf_bytes(3 * 1024 * 1024, "big")})
        h.hub.delay_s = 0.02
        v = _start(h, "example-org/Big-GGUF", "")
        end = time.monotonic() + 10
        while time.monotonic() < end and not (next((j for j in h.api("GET", "local/downloads")[1]["jobs"] if j["job"] == v["job"]), {}).get("completed") or 0):
            time.sleep(0.05)
        status, c = h.api("POST", f"local/download/{v['job']}/cancel")
        ctx.check(f"the cancel route, got {status} {c}", status == 200 and c["cancelling"])
        done = h.wait_job(v["job"])
        ctx.check(f"cancelled, the part kept, got {done.get('say')}", done.get("cancelled") and "part file keeps" in done["say"])
        listing = h.api("GET", "local/hf/dirs")[1]["dirs"][0]
        ctx.check(f"the folder lists the part, got {listing['partial']}", listing["partial"] and listing["partial"][0]["repo"] == "example-org/Big-GGUF")
        h.hub.delay_s = 0.0
        again = _start(h, "example-org/Big-GGUF", "")
        ctx.check("the next download ends ok", h.wait_job(again["job"]).get("ok"))
        ranges = [r["range"] for r in h.hub.resolves()]
        ctx.check(f"it resumed with a Range, got {ranges}", ranges[-1] and ranges[-1].startswith("bytes="))
        ctx.check("the cancel route 404s an unknown job", h.api("POST", "local/download/dl-nope/cancel")[0] == 404)


@test
def test_the_folder_listing_is_read_again_when_one_lands(ctx: Ctx):
    with HfHome() as h:
        before = h.api("GET", "local/hf/dirs")[1]
        ctx.check(f"empty before, got {before['dirs']}", before["dirs"][0]["models"] == [] and before["host"] == "box")
        v = _start(h)
        h.wait_job(v["job"])
        after = h.api("GET", "local/hf/dirs")[1]
        rows = after["dirs"][0]["models"]
        row = rows[0] if rows else {}
        ctx.check(f"the model is listed, got {[(r['repo'], r['file'], r['kind']) for r in rows]}",
                  len(rows) == 1 and row["repo"] == GGUF and row["file"] == "Tiny-1B-Q4_K_M.gguf" and row["kind"] == "gguf" and row["hub"])
        ctx.check(f"its card, its fit on box and the serve line, got {row.get('fit')} {row.get('cli')}",
                  row["card"].get("chips") is not None and row["fit"]["level"] in ("fits", "tight") and "box" in row["fits"]
                  and row["cli"]["serve"] == f"halo local serve {row['path']}" and row["context"] == 40960)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))

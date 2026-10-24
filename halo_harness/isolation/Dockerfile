# The Halo Harness worker image (Halo 3.1.8.0 R5, docs/ISOLATION.md).
# `halo isolation build` builds it as halo-harness-worker:<version> with
# HALO_VERSION set to the harness that builds it; `halo isolation image`
# prints this file. A container worker runs `halo -p ...` in /work (the
# lane's worktree), with the run folder at /run and a scoped state dir at
# /root/.halo; nothing else of the host is inside.
FROM python:3.12-slim

ARG HALO_VERSION
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates ripgrep \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "git+https://github.com/roloVibes/Halo-Harness.git@v${HALO_VERSION}"

ENV PYTHONIOENCODING=utf-8
WORKDIR /work
CMD ["halo", "--version"]

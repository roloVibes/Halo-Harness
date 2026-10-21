"""The doc-review fixture pack's MCP server entry point (never started by
the tests; its configuration is what they read). It imports halo_harness.ext
only (tests/test_ext_api.py checks every fixture pack for that)."""

import sys

from halo_harness.ext import API_VERSION, get_config


def main() -> int:
    style = get_config("doc-review", "style", "short")
    sys.stdout.write(f"lint server for extension API {API_VERSION}, style {style}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

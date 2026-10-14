"""halo_harness.media -- ComfyUI as a craft app (Halo 3.0.4.0 round R1).

A stdlib HTTP client for a ComfyUI server (comfy_client.py), UI-format to
API-format graph conversion with `set` overrides and `only` pruning
(comfy_graph.py, comfy_ui.py), the operations every surface shares
(comfy_ops.py), the server's own error text (comfy_errors.py), the
`mcp__comfyui__*` stdio MCP server (comfy_server.py) and the `halo media`
command family (cli.py, setup_cli.py). The server may run on another host: outputs are
always read back over HTTP, never from a disk path.
"""

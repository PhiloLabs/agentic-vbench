"""
MCP server that proxies tool execution into a running, network-isolated
Docker container. The agent process (this MCP server's client) runs on the
host with normal network access to reach the model API; every actual task
action (bash commands, file reads/writes) happens via `docker exec` into a
container started with --network none, so the agent never has a real network
path to the task's data source.
"""

import base64
import subprocess
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

CONTAINER = sys.argv[1] if len(sys.argv) > 1 else "calib-container"
mcp = FastMCP("container-exec")


@mcp.tool()
def bash(command: str, timeout_sec: int = 600) -> str:
    """Run a shell command inside the isolated task container (network
    disabled) and return combined stdout+stderr. Working directory is
    /workspace."""
    try:
        r = subprocess.run(
            ["docker", "exec", "-w", "/workspace", CONTAINER, "bash", "-c", command],
            capture_output=True, text=True, timeout=timeout_sec,
        )
        out = r.stdout + r.stderr
        return "%s\n[exit code: %d]" % (out, r.returncode)
    except subprocess.TimeoutExpired:
        return "[TIMEOUT after %ds]" % timeout_sec


@mcp.tool()
def read_image(path: str) -> ImageContent:
    """Read an image file from inside the isolated task container and
    return it for visual inspection. Path is absolute inside the
    container (e.g. /workspace/work/frame_0042.png)."""
    r = subprocess.run(["docker", "exec", CONTAINER, "cat", path],
                        capture_output=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError("could not read %s: %s" % (path, r.stderr.decode(errors="replace")))
    ext = path.rsplit(".", 1)[-1].lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
    return ImageContent(type="image", data=base64.b64encode(r.stdout).decode(), mimeType=mime)


if __name__ == "__main__":
    mcp.run(transport="stdio")

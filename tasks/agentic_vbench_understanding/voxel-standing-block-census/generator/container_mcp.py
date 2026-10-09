#!/usr/bin/env python3
"""Proxy every task action into a frozen `--network none` task container.

The agent CLI runs on the host (it needs network to reach its own API).
Everything it does to the task environment goes through the two tools below,
so the materials, the working files and the answer all live inside the
container that `environment/Dockerfile` builds.

stdio JSON-RPC, no third-party imports.
"""
import json, os, subprocess, sys, uuid

CT      = os.environ.get("AVB_CT", "avb_task")
STAGING = os.environ["AVB_STAGING"]          # host dir the agent may read
MAXOUT  = 20000
os.makedirs(STAGING, exist_ok=True)

LOG = open(os.path.join(STAGING, os.pardir, "mcp_calls.log"), "a", buffering=1)


def log(kind, payload):
    LOG.write(json.dumps({"kind": kind, **payload})[:4000] + "\n")


def clip(s):
    if len(s) <= MAXOUT:
        return s
    half = MAXOUT // 2
    return s[:half] + f"\n...[{len(s)-MAXOUT} chars elided]...\n" + s[-half:]


def t_exec(args):
    cmd = args.get("command", "")
    timeout = float(args.get("timeout_sec", 900))
    log("exec", {"command": cmd, "timeout": timeout})
    try:
        r = subprocess.run(
            ["docker", "exec", "-w", "/workspace", CT, "bash", "-lc", cmd],
            capture_output=True, text=True, timeout=timeout, errors="replace")
        out = f"exit_code: {r.returncode}\n"
        if r.stdout:
            out += "--- stdout ---\n" + r.stdout
        if r.stderr:
            out += "\n--- stderr ---\n" + r.stderr
        if not r.stdout and not r.stderr:
            out += "(no output)"
        return clip(out)
    except subprocess.TimeoutExpired:
        return f"exit_code: -1\ncommand timed out after {timeout}s"


def t_fetch(args):
    path = args.get("path", "")
    if not path.startswith("/workspace/"):
        return "error: path must be absolute inside the container, under /workspace/"
    ext = os.path.splitext(path)[1] or ".bin"
    host = os.path.join(STAGING, uuid.uuid4().hex[:12] + ext)
    log("fetch", {"path": path, "host": host})
    r = subprocess.run(["docker", "cp", f"{CT}:{path}", host],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "error: " + (r.stderr.strip() or "docker cp failed")
    size = os.path.getsize(host)
    return (f"copied {path} ({size} bytes) out to the host at:\n{host}\n"
            "Open it with the view_image tool using exactly that path.")


TOOLS = [
    {"name": "exec",
     "description": (
         "Run a shell command inside the task container. The working directory "
         "is /workspace. The recording is at /workspace/materials/session.mp4, "
         "your scratch space is /workspace/work, and your answer belongs at "
         "/workspace/output/solution.json. python3, ffmpeg, numpy, scipy, "
         "opencv, scikit-image and pillow are installed. The container has no "
         "network. This is the only way to touch the task environment."),
     "inputSchema": {"type": "object", "properties": {
         "command": {"type": "string", "description": "bash -lc command line"},
         "timeout_sec": {"type": "number", "description": "default 900"}},
         "required": ["command"]},
     "annotations": {"title": "Run a command in the task container",
                     "readOnlyHint": False, "destructiveHint": False,
                     "idempotentHint": False, "openWorldHint": False}},
    {"name": "fetch",
     "description": (
         "Copy one file out of the task container so you can look at it. "
         "Give an absolute container path under /workspace; you get back a "
         "host path to hand to view_image. Use it on frames you have written "
         "inside the container, e.g. /workspace/work/f00123.jpg."),
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string"}}, "required": ["path"]},
     "annotations": {"title": "Copy a file out of the task container",
                     "readOnlyHint": True, "destructiveHint": False,
                     "idempotentHint": True, "openWorldHint": False}},
]
HANDLERS = {"exec": t_exec, "fetch": t_fetch}


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, rid = req.get("method"), req.get("id")
        if rid is None:                      # notification
            continue
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": req.get("params", {}).get(
                    "protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "avb-task-container", "version": "1.0"}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            p = req.get("params", {})
            fn = HANDLERS.get(p.get("name"))
            if fn is None:
                send({"jsonrpc": "2.0", "id": rid, "error": {
                    "code": -32601, "message": "unknown tool"}})
                continue
            try:
                text = fn(p.get("arguments") or {})
            except Exception as e:                      # noqa: BLE001
                text = f"error: {type(e).__name__}: {e}"
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": text}],
                "isError": text.startswith("error:")}})
        else:
            send({"jsonrpc": "2.0", "id": rid, "result": {}})


if __name__ == "__main__":
    main()

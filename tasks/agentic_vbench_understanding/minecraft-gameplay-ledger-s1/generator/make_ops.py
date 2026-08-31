#!/usr/bin/env python3
"""Write a Paper `ops.json` granting level-4 op to the offline-mode bots.

Why this exists: on an offline-mode server a player's UUID is the deterministic name-based UUID
`uuid3(md5, "OfflinePlayer:<name>")`, so op can be granted BEFORE anyone connects. Without it the
bots' `/setblock`, `/summon` and `/locate` calls come back as *"Unknown command"* -- Brigadier hides
commands a player is not permitted to run -- which reads exactly like a version-incompatibility bug.
That mis-diagnosis cost one full authentic session (0 events recorded).

    make_ops.py <server_dir> [name ...]
"""
import hashlib, json, sys, uuid


def offline_uuid(name: str) -> str:
    """The UUID a vanilla/Paper server assigns to `name` when online-mode=false."""
    h = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode("utf-8")).digest())
    h[6] = (h[6] & 0x0F) | 0x30          # version 3
    h[8] = (h[8] & 0x3F) | 0x80          # RFC 4122 variant
    return str(uuid.UUID(bytes=bytes(h)))


def main() -> None:
    srv = sys.argv[1]
    names = sys.argv[2:] or ["Builder", "Camera", "Director", "Probe"]
    ops = [{"uuid": offline_uuid(n), "name": n, "level": 4, "bypassesPlayerLimit": True}
           for n in names]
    with open(f"{srv}/ops.json", "w") as fh:
        json.dump(ops, fh, indent=2)
    for o in ops:
        print(f"op {o['name']:9s} {o['uuid']}")


if __name__ == "__main__":
    # self-test against the known-good value already in the 1.16.5 server's ops.json
    assert offline_uuid("Builder") == "a1b1b4de-45be-3659-b2e1-5c9a1693e63b", offline_uuid("Builder")
    main()

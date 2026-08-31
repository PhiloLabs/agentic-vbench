#!/bin/bash
# Download a vanilla Minecraft 1.16.5 client (jar + libraries + assets) into a self-contained
# directory so it can be launched offline and headless. This is the "authentic renderer" path:
# the real client renders crack, hurt-flash, hand-swing, particles and sound natively, so none
# of it has to be composited. The mineflayer bot logic is reused UNCHANGED — the client only
# joins as a spectator camera that follows the bot.
set -eux
MC=${1:?mc dir}
VER=${2:-1.16.5}
mkdir -p "$MC"/{libraries,assets/objects,assets/indexes,natives,bin}
cd "$MC"

j() { /usr/bin/python3 -c "import json,sys;print(json.load(open(sys.argv[1]))$1)" "$2"; }

# 1) version manifest -> the 1.16.5 version json
curl -sSL https://piston-meta.mojang.com/mc/game/version_manifest_v2.json -o manifest.json
VURL=$(/usr/bin/python3 -c "import json;m=json.load(open('manifest.json'));print(next(v['url'] for v in m['versions'] if v['id']=='$VER'))")
curl -sSL "$VURL" -o version.json
AIDX=$(/usr/bin/python3 -c "import json;print(json.load(open('version.json'))['assetIndex']['id'])")
echo "ASSET_INDEX=$AIDX" > asset_index.txt

# 2) client jar
CJAR=$(j "['downloads']['client']['url']" version.json)
curl -sSL "$CJAR" -o bin/client.jar

# 3) libraries (skip natives rule-mismatch; grab linux natives where present)
/usr/bin/python3 - "$MC" <<'PY'
import json, os, sys, urllib.request
mc = sys.argv[1]
v = json.load(open(os.path.join(mc, "version.json")))
cp = []
for lib in v["libraries"]:
    rules = lib.get("rules", [])
    allow = True
    for r in rules:
        act = r["action"] == "allow"
        os_name = r.get("os", {}).get("name")
        if os_name is None:
            allow = act
        elif os_name == "linux":
            allow = act
        elif act:
            allow = False
    if not allow:
        continue
    dl = lib.get("downloads", {})
    art = dl.get("artifact")
    if art:
        dst = os.path.join(mc, "libraries", art["path"].replace("/", "_"))
        if not os.path.exists(dst):
            urllib.request.urlretrieve(art["url"], dst)
        cp.append(dst)
    nat = lib.get("natives", {}).get("linux")
    if nat:
        cl = dl.get("classifiers", {}).get(nat.replace("${arch}", "64"))
        if cl:
            nj = os.path.join(mc, "natives", os.path.basename(cl["path"]))
            if not os.path.exists(nj):
                urllib.request.urlretrieve(cl["url"], nj)
            os.system(f"cd {mc}/natives && unzip -oq {nj} -x 'META-INF/*' 2>/dev/null || true")
open(os.path.join(mc, "classpath.txt"), "w").write(":".join(cp + [os.path.join(mc, "bin/client.jar")]))
print("libraries:", len(cp))
# asset index
ai = v["assetIndex"]
idx = os.path.join(mc, "assets/indexes", ai["id"] + ".json")
urllib.request.urlretrieve(ai["url"], idx)
print("asset index:", ai["id"])
PY

# 4) assets (objects) — needed for textures/sound; fetch from resources CDN
/usr/bin/python3 - "$MC" <<'PY'
import json, os, sys, urllib.request, concurrent.futures
mc = sys.argv[1]
ai = [f for f in os.listdir(os.path.join(mc, "assets/indexes"))][0]
idx = json.load(open(os.path.join(mc, "assets/indexes", ai)))
objs = idx["objects"]
def get(h):
    d = os.path.join(mc, "assets/objects", h[:2])
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, h)
    if not os.path.exists(p):
        urllib.request.urlretrieve(f"https://resources.download.minecraft.net/{h[:2]}/{h}", p)
items = [o["hash"] for o in objs.values()]
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
    list(ex.map(get, items))
print("assets:", len(items))
PY
echo "CLIENT_READY $VER"

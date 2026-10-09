-- Scripted camera rig for AgenticVBench capture, v3.
--
-- v1 and v2 both asked "which block, when". Astra answered that at 0.32 and
-- 0.73 because a voxel game's textures are stock: cobble always looks like
-- cobble, so block identity is a one-time calibration. v3 stops asking it.
--
-- The rig now flies a closed circle, so the crosshair retraces the same ring
-- of ground every lap. When it finds a block that it placed on an earlier lap
-- it digs that block out and the ledger records WHEN THE BLOCK WAS PLACED.
-- Two blocks of the same type look identical; only the history separates
-- them, so the answer cannot come from appearance at the moment of the dig.
--
-- Kept from v2 for measured reasons: height 12 and speed 6 (block about 47 px),
-- the texture-measured confusable palette, GO-file plus three-flash clock sync,
-- hotbar and wielditem off, noon with the weather cycle held.

local LOGPATH   = minetest.get_worldpath() .. "/avb_events.log"
local GOPATH    = minetest.get_worldpath() .. "/GO"
local SPEED     = 6.0
local HEIGHT    = 12.0
local PITCH     = math.rad(-34)
local REACH     = 30
local ACT_EVERY = 1.3
-- The route went circle, then trochoid, then this, and the reason each time
-- was the age distribution. A circle revisits a spot only at whole multiples
-- of its period: the 240 s smoke came back with fourteen of twenty ages at
-- exactly 46.5 s, so "now minus the lap time" would have answered the second
-- timestamp for free. The trochoid only smeared those bands to 42-51 s,
-- because with an 8 node wobble against a 10-35 node view cone the blocks in
-- sight are still all from one lap ago. Any quasi-periodic route does this.
-- So the rig now walks: the turn rate is a damped random walk, and it is
-- pulled back whenever it drifts past RMAX. Revisit intervals for a random
-- walk over a bounded region are broadly distributed by construction.
--
-- That was wrong too. The 420 s smoke banded at 49, 101, 154, 206, 258 and
-- 310: an equal-speed walk confined to a disc still has a characteristic
-- return time, and a smooth heading makes the return-time distribution peak
-- at it rather than spread. Three route shapes, three banded histograms.
-- Geometry is not going to produce the distribution, so it no longer decides
-- it: every block is given a lifetime when it goes down, drawn log-uniformly
-- over LIFE_MIN..LIFE_MAX, and it only becomes diggable once that has run
-- out. The walk still decides the exact moment, which adds the travel time on
-- top, but the shape of the age distribution is now specified, not emergent.
-- Astra scored 0.3613 on the 900 s pilot, and taking the fields away one at a
-- time put the cost where the design meant it: removals alone 0.7731, plus
-- the block type 0.6218, plus the placement time 0.3613. It binds 43 of the
-- 74 removals it finds, and when it is right it is right to a tenth of a
-- second. What it says goes wrong is "repeated blocks near the same terrain
-- features", so the quantity that decides binding is how many same-type
-- blocks sit near the one that vanished. Three hundred placements over a
-- disc of radius 50 is one per 26 square nodes; radius 20 is one per four.
local RMAX      = 20.0
local TURN_MAX  = math.rad(9)    -- rad/s, about a 40 s turn at full rate
local TURN_NOISE= math.rad(26)
local TURN_DAMP = 0.55
local PULL      = 0.9
-- The number a solver has to choose between, when it sees a block go and has
-- to say when that one was put down, is the count of same-type placements
-- inside the age range: placement rate times the range, over the number of
-- block types. On the first 900 s pilot that was about four, and handing an
-- attacker the full placement list and the rule "same type, age nearest the
-- median" scored 0.2518. Raising the rate and widening the range raises the
-- count; the range is capped by the length of the capture, which is why this
-- task, unlike the two before it, does get harder with a longer video.
-- The lifetime range has to scale with the capture. At 620 s in a 1800 s
-- video every early block is gone before the end, the standing set stops
-- growing and settles near 150; spread over twenty types that is eight per
-- cell, the regime the sweep measured as the easiest of all. The range now
-- reaches most of the way across the recording, so the census keeps climbing
-- and each cell holds a number that is hard to hit by luck.
local LIFE_MIN  = 60.0
local LIFE_MAX  = 1700.0
local GOAL_PULL = 0.50     -- soft, so the rig meanders instead of beelining
local GOAL_GIVEUP = 90.0
-- Projecting every logged event onto its frame showed all of them in shot but
-- the dug block only 19 px across, because candidates were taken uniformly
-- from a 10-35 node band and most of that band's area is at the far end. At
-- 19 px a confusable block on similar-coloured ground cannot be named, which
-- would have mixed "cannot read it" into a score meant to measure "cannot
-- place it in time". Narrow the band and take the nearest.
local VIEW_NEAR = 8.0
local VIEW_FAR  = 18.0
local VIEW_ANG  = math.rad(35)

-- v4 asks for the standing census, not the ledger, so the palette is six
-- blocks nobody could mistake for one another. A fine-grained vocabulary was
-- measured to be worth nothing on v2 (mean texture distance 3.707 down to
-- 1.842 changed the identification rate not at all), and here it would only
-- mix "could not tell brick from clay" into a number meant to read "could not
-- keep count". Six types also leaves about twenty-two blocks of each type
-- standing at once, and an exact count is hard to hit by luck at twenty-two
-- where it is easy at the seven that twenty types gave.
local PLACEABLE = {
  "mcl_core:brick_block",                    -- red
  "mcl_books:bookshelf",                     -- books on shelves
  "mcl_core:gravel",                         -- speckled grey
  "mcl_core:birchwood",                      -- pale
  "mcl_core:mossycobble",                    -- green grey
  "mcl_colorblocks:hardened_clay_orange",    -- orange
}

local DRIFT_EVERY    = 120
-- Share for rank k, dealt to a random type each window. Built as 1/k^0.8 and
-- normalised, so with twenty types the leading share is about a fifth and the
-- tail still gets placed. A flat share would let a solver read the count per
-- type off the running total.
local WEIGHT_PROFILE = {}

local PALETTE = {}
-- rank k holds palette index ORDER[k] and cumulative weight CUM[k]. The first
-- version stored the cumulative sums at the shuffled indices but then walked
-- the array in palette order, so the array was not monotonic and the scan
-- returned whichever early index happened to hold a large partial sum. Two
-- types took every placement: the ground truth came back with brick_block at
-- 157 standing and birchwood at 0 for the whole video.
local ORDER, CUM, wt_next = {}, {}, -1e9

minetest.register_on_mods_loaded(function()
  for _, n in ipairs(PLACEABLE) do
    if minetest.registered_nodes[n] then PALETTE[#PALETTE + 1] = n
    else minetest.log("error", "[avbcam] missing node " .. n) end
  end
  local acc = 0
  for k = 1, #PALETTE do
    WEIGHT_PROFILE[k] = 1 / (k ^ 0.8)
    acc = acc + WEIGHT_PROFILE[k]
  end
  for k = 1, #PALETTE do WEIGHT_PROFILE[k] = WEIGHT_PROFILE[k] / acc end
  minetest.log("action", string.format("[avbcam] palette %d of %d, top share %.3f",
    #PALETTE, #PLACEABLE, WEIGHT_PROFILE[1] or 0))
end)

local function redraw_weights(now)
  local n = #PALETTE
  ORDER = {}
  for i = 1, n do ORDER[i] = i end
  for i = n, 2, -1 do
    local j = math.random(i)
    ORDER[i], ORDER[j] = ORDER[j], ORDER[i]
  end
  CUM = {}
  local acc = 0
  for k = 1, n do
    acc = acc + (WEIGHT_PROFILE[k] or 0.02)
    CUM[k] = acc
  end
  local parts = {}
  for k = 1, n do
    parts[#parts + 1] = string.format("%s=%.2f", PALETTE[ORDER[k]],
      CUM[k] - (k > 1 and CUM[k - 1] or 0))
  end
  minetest.log("action", string.format("[avbcam] weights t=%.1f %s", now,
    table.concat(parts, " ")))
end

local function pick_block(now)
  local n = #PALETTE
  if n == 0 then return nil end
  if now >= wt_next then
    wt_next = now + DRIFT_EVERY
    redraw_weights(now)
  end
  local r = math.random() * CUM[n]
  for k = 1, n do
    if r <= CUM[k] then return PALETTE[ORDER[k]] end
  end
  return PALETTE[ORDER[n]]
end

local HUD_OFF = {hotbar = false, wielditem = false, healthbar = false,
                 breathbar = false, minimap = false, chat = false,
                 basic_debug = false}

local t, actacc, hudacc = 0, 0, 0
local yaw, turn = 0, 0
local CX, CZ = 0, 0
local base_y = 20
local placed = {}          -- "x,y,z" -> {name =, t =, pos =, life =}
local goal, goal_since = nil, 0
local n_place, n_redig = 0, 0
local ev_count = {}
local rig, cam_player, running = nil, nil, false

local function strip_hud(player)
  local ok, all = pcall(function() return player:hud_get_all() end)
  if not ok or not all then return 0 end
  local n = 0
  for id, def in pairs(all) do
    local txt = def.text
    if type(txt) == "string" and (txt:find("hotbar") or txt:find("inventory")) then
      player:hud_remove(id); n = n + 1
    end
  end
  return n
end

local function hash(p) return p.x .. "," .. p.y .. "," .. p.z end

-- Uniform, not log-uniform. Log-uniform put 17 per cent of its mass under 40 s
-- and the 600 s smoke duly piled fourteen of eighty-two ages into one three
-- second window, which is a free guess. A flat distribution over the range is
-- the one that leaves a prior with nothing to grip.
local function draw_life()
  return LIFE_MIN + math.random() * (LIFE_MAX - LIFE_MIN)
end

-- Every row carries the camera pose. Without it there is no way to check
-- afterwards that a logged event was actually inside the frame, and a
-- machine-truth log of things that happened off screen is not a usable
-- answer key however well the clock is aligned.
local cam_pose = {x = 0, y = 0, z = 0, yaw = 0}
local function log(action, name, pos, extra)
  local f = io.open(LOGPATH, "a")
  if not f then return end
  f:write(string.format("%.3f\t%s\t%s\t%d,%d,%d\t%s\t%.2f,%.2f,%.2f,%.4f\n",
    t, action, name, pos.x, pos.y, pos.z, extra or "-",
    cam_pose.x, cam_pose.y, cam_pose.z, cam_pose.yaw))
  f:close()
end

local FLASH_AT = {1.0, 2.0, 4.0}
local FLASH_LEN = 0.30
local function flash(player)
  for _, at in ipairs(FLASH_AT) do
    minetest.after(at, function()
      if not player or not player:is_player() then return end
      local id = player:hud_add({
        hud_elem_type = "image", text = "[fill:16x16:#ffffff",
        position = {x = 0.5, y = 0.5}, scale = {x = -100, y = -100},
        alignment = {x = 0, y = 0}, z_index = 1000,
      })
      log("sync", "flash", {x = 0, y = 0, z = 0})
      minetest.after(FLASH_LEN, function()
        if player and player:is_player() and id then player:hud_remove(id) end
      end)
    end)
  end
end

local function clear_sky()
  minetest.set_timeofday(0.5)
  if mcl_weather then
    pcall(mcl_weather.change_weather, "none", nil, "avbcam")
    pcall(function() vl_tuning.set_setting("gamerule:doWeatherCycle", false) end)
    pcall(function() mcl_weather.skycolor.update_sky_color() end)
  end
end

local function is_liquid(name)
  local d = minetest.registered_nodes[name]
  return d and d.liquidtype and d.liquidtype ~= "none"
end

-- Highest surface within a few nodes, so the rig clears a tree instead of
-- flying into its canopy. HEIGHT above the ground directly below is not
-- enough next to a jungle tree twenty nodes tall.
local function clearance_y(x, z)
  local m = nil
  for _, d in ipairs({{0,0},{6,0},{-6,0},{0,6},{0,-6},{5,5},{-5,-5},{5,-5},{-5,5}}) do
    local g = nil
    for y = 120, 0, -1 do
      local n = minetest.get_node_or_nil({x = x + d[1], y = y, z = z + d[2]})
      if n and n.name ~= "air" and n.name ~= "ignore" then g = y break end
    end
    if g and (not m or g > m) then m = g end
  end
  return m
end

-- Name of the top solid node in a column, for judging what the surface is
-- made of. The 600 s smoke landed on a jungle: the blocks stood out fine
-- against the canopy, but one patch of treetop looks exactly like the next,
-- so "which spot is this" would have been impossible rather than hard. The
-- centre picker now avoids foliage and looks for open ground.
local function top_name(x, z)
  for y = 90, 0, -1 do
    local n = minetest.get_node_or_nil({x = x, y = y, z = z})
    if n and n.name ~= "air" and n.name ~= "ignore" then return n.name end
  end
  return nil
end

local function is_foliage(name)
  if not name then return true end
  local d = minetest.registered_nodes[name]
  if not d then return true end
  local g = d.groups or {}
  if g.leaves or g.tree or g.plant or g.flower then return true end
  if d.walkable == false then return true end
  return false
end

local function ground_y(x, z)
  for y = 90, 0, -1 do
    local n = minetest.get_node_or_nil({x = x, y = y, z = z})
    if n and n.name ~= "air" and n.name ~= "ignore" and not is_liquid(n.name) then
      return y
    end
  end
  return nil
end

local function dir_of(a)
  return {x = -math.sin(a) * math.cos(PITCH),
          y =  math.sin(PITCH),
          z =  math.cos(a) * math.cos(PITCH)}
end

-- Score a candidate centre by how much of its ring is solid ground. The rig
-- flies the whole circle for the entire capture, so a ring crossing water or
-- unloaded chunks would waste laps.
-- The rig keeps a fixed downward pitch, so how far ahead the crosshair lands
-- depends on the relief in front of it. The first smoke test picked a ring
-- spanning 14 nodes of height and the crosshair distance swung between about
-- 10 and 40 nodes, which is why the same ground was never retraced. Score a
-- candidate centre on flatness, not just on having ground at all.
local function ring_score(cx, cz)
  local ok, ys, n, fol = 0, {}, 0, 0
  for i = 0, 23 do
    local a = i * math.pi / 12
    for _, rr in ipairs({8, 18, 28, 38, 46, 54}) do
      n = n + 1
      local x = math.floor(cx + rr * math.cos(a) + 0.5)
      local z = math.floor(cz + rr * math.sin(a) + 0.5)
      local g = ground_y(x, z)
      if g then
        ok = ok + 1; ys[#ys + 1] = g
        if is_foliage(top_name(x, z)) then fol = fol + 1 end
      end
    end
  end
  if #ys == 0 then return -1, 20, 99 end
  local mean, lo, hi = 0, 1e9, -1e9
  for _, y in ipairs(ys) do
    mean = mean + y
    if y < lo then lo = y end
    if y > hi then hi = y end
  end
  mean = mean / #ys
  local sd = 0
  for _, y in ipairs(ys) do sd = sd + (y - mean) ^ 2 end
  sd = math.sqrt(sd / #ys)
  -- open ground first, then flat. A canopy scores worse than a bare hillside.
  return (48 * ok / n) - 3 * sd - 200 * (fol / math.max(1, ok)), mean, sd
end

-- The seed is chosen offline by the probe above and the centre it validated
-- is pinned in the config, so the capture does not re-decide the terrain.
local pick_centre_auto
local function pick_centre()
  local cfg = minetest.settings:get("avb_centre")
  if cfg then
    local cx, cz = cfg:match("^(-?%d+),(-?%d+)$")
    if cx then
      local _, mean, sd = ring_score(tonumber(cx), tonumber(cz))
      return tonumber(cx), tonumber(cz), mean, sd
    end
  end
  return pick_centre_auto()
end

function pick_centre_auto()
  local best, bs, bm, bsd = nil, -1e9, 20, 99
  for _, c in ipairs({{0,0},{60,0},{0,60},{-60,0},{0,-60},{60,60},{-60,-60},
                      {60,-60},{-60,60},{120,0},{0,120},{-120,0},{0,-120},
                      {120,120},{-120,-120},{180,0},{0,180}}) do
    local s, mean, sd = ring_score(c[1], c[2])
    if s > bs then bs, bm, bsd, best = s, mean, sd, c end
  end
  return (best and best[1]) or 0, (best and best[2]) or 0, bm, bsd
end

minetest.register_entity("avbcam:rig", {
  initial_properties = {
    physical = false, collide_with_objects = false, pointable = false,
    visual = "sprite", visual_size = {x = 0.01, y = 0.01},
    textures = {"blank.png"}, static_save = false, glow = 0,
  },
  on_step = function(self) end,
})

local function wrap(a)
  while a >  math.pi do a = a - 2 * math.pi end
  while a < -math.pi do a = a + 2 * math.pi end
  return a
end

local function launch()
  if running or not cam_player then return end
  local ok
  CX, CZ, base_y, ok = pick_centre()
  turn = 0
  local sx, sz = CX + 20, CZ
  local gy = ground_y(math.floor(sx + 0.5), math.floor(sz + 0.5)) or base_y
  local start = {x = sx, y = gy + HEIGHT, z = sz}
  yaw = math.random() * 2 * math.pi
  rig = minetest.add_entity(start, "avbcam:rig")
  if not rig then return end
  cam_player:set_attach(rig, "", {x = 0, y = 0, z = 0}, {x = 0, y = 0, z = 0})
  cam_player:set_look_horizontal(yaw)
  cam_player:set_look_vertical(-PITCH)
  clear_sky()
  do
    local seen, nn = {}, 0
    for i = 0, 11 do
      local a = i * math.pi / 6
      for _, rr in ipairs({14, 28, 42, 50}) do
        local tn = top_name(math.floor(CX + rr * math.cos(a) + 0.5),
                            math.floor(CZ + rr * math.sin(a) + 0.5))
        if tn then seen[tn] = (seen[tn] or 0) + 1; nn = nn + 1 end
      end
    end
    local parts = {}
    for k, v in pairs(seen) do parts[#parts + 1] = string.format("%s=%d", k, v) end
    minetest.log("action", "[avbcam] surface " .. nn .. ": " .. table.concat(parts, " "))
    local f = cam_player:hud_get_flags()
    local fp = {}
    for k, v in pairs(f) do fp[#fp + 1] = k .. "=" .. tostring(v) end
    minetest.log("action", "[avbcam] hudflags " .. table.concat(fp, " "))
  end
  t, running = 0, true
  log("start", "-", start, string.format("centre=%d,%d rmax=%.0f _=%.0f relief_sd=%.1f",
      CX, CZ, RMAX, 0, ok))
  flash(cam_player)
  minetest.log("action", string.format("[avbcam] launched centre %d,%d relief sd %.1f", CX, CZ, ok))
end

local function wait_for_go()
  local f = io.open(GOPATH, "r")
  if f then f:close(); launch(); return end
  minetest.after(0.25, wait_for_go)
end

-- Offline seed probe. With avb_probe = true the mod emits one line of world
-- statistics a few seconds after the map is up and shuts the server down, so
-- a seed can be judged in half a minute without a client or a capture.
-- Offline seed probe. With avb_probe = true the mod forces the map around the
-- origin into existence, reports what the surface is made of and how much
-- relief it has, then shuts the server down: a seed can be judged in under a
-- minute with no client and no capture. Without the emerge it reports nothing
-- at all, because a server with no player connected generates no map.
if minetest.settings:get_bool("avb_probe") then
  local P1 = {x = -70, y = 0,   z = -70}
  local P2 = {x =  70, y = 140, z =  70}
  minetest.after(2, function()
    minetest.emerge_area(P1, P2, function(_, _, remaining)
      if remaining ~= 0 then return end
      local fol, tot, ys = 0, 0, {}
      for i = 0, 23 do
        local a = i * math.pi / 12
        for _, rr in ipairs({8, 18, 28, 38, 46, 54}) do
          local x = math.floor(rr * math.cos(a) + 0.5)
          local z = math.floor(rr * math.sin(a) + 0.5)
          local tn = top_name(x, z)
          local g = ground_y(x, z)
          if tn then
            tot = tot + 1
            if is_foliage(tn) then fol = fol + 1 end
          end
          if g then ys[#ys + 1] = g end
        end
      end
      local mean, sd = 0, 0
      for _, y in ipairs(ys) do mean = mean + y end
      if #ys > 0 then mean = mean / #ys end
      for _, y in ipairs(ys) do sd = sd + (y - mean) ^ 2 end
      if #ys > 0 then sd = math.sqrt(sd / #ys) end
      minetest.log("action", string.format(
        "[avbprobe] seed=%s ground=%d/%d foliage=%d/%d relief_sd=%.1f y=%.0f",
        tostring(minetest.get_mapgen_setting("seed")), #ys, tot, fol, tot, sd, mean))
      minetest.after(1, function() minetest.request_shutdown() end)
    end)
  end)
end

minetest.register_on_joinplayer(function(player)
  local name = player:get_player_name()
  minetest.set_player_privs(name, {interact=true, shout=true, fly=true, fast=true,
                                   noclip=true, give=true, settime=true,
                                   teleport=true, debug=true, server=true})
  player:set_physics_override({speed = 0, jump = 0, gravity = 0})
  player:hud_set_flags(HUD_OFF)
  minetest.after(0.5, function()
    minetest.log("action", "[avbcam] stripped " .. strip_hud(player) .. " hud elems")
  end)
  cam_player = player
  minetest.after(1.0, wait_for_go)
end)

-- Nearest block this rig placed earlier, within NEAR_R horizontally and one
-- node vertically of the crosshair. Stale entries (the node is no longer what
-- we put there) are dropped as they are found.
local function alive(k, rec)
  local nd = minetest.get_node_or_nil(rec.pos)
  if nd and nd.name == rec.name then return true end
  placed[k] = nil
  return false
end

-- The block whose lifetime ran out longest ago. This is the rig's next
-- destination; it is not dug until it actually comes into view.
local function pick_goal()
  local best, bo = nil, 0
  for k, rec in pairs(placed) do
    local over = (t - rec.t) - rec.life
    if over > bo and alive(k, rec) then bo, best = over, {key = k, rec = rec} end
  end
  return best
end

-- Any of our expired blocks that is on screen right now. The goal is
-- preferred, but if the walk carries another expired one through the view
-- cone first it is taken, which keeps the camera from beelining. Among the
-- rest the nearest wins, so the block is as large on screen as it gets.
local function visible_expired(cx2, cz2, hx, hz)
  local hits, dead = {}, nil
  for k, rec in pairs(placed) do
    if (t - rec.t) >= rec.life then
      local dx, dz = rec.pos.x - cx2, rec.pos.z - cz2
      local d = math.sqrt(dx * dx + dz * dz)
      if d >= VIEW_NEAR and d <= VIEW_FAR and (dx * hx + dz * hz) / d >= math.cos(VIEW_ANG) then
        local nd = minetest.get_node_or_nil(rec.pos)
        if nd and nd.name == rec.name then
          hits[#hits + 1] = {pos = rec.pos, rec = rec, key = k}
        else
          dead = dead or {}; dead[#dead + 1] = k
        end
      end
    end
  end
  if dead then for _, k in ipairs(dead) do placed[k] = nil end end
  if #hits == 0 then return nil end
  for _, h in ipairs(hits) do
    if goal and h.key == goal.key then return h end
  end
  local best, bd = nil, 1e9
  for _, h in ipairs(hits) do
    local dx, dz = h.pos.x - cx2, h.pos.z - cz2
    local d = dx * dx + dz * dz
    if d < bd then bd, best = d, h end
  end
  return best
end

-- A column within a few nodes of the crosshair whose surface is untouched
-- terrain and which has air above it. Tried in a random order so the rig does
-- not always drift the same way.
local function free_spot_near(p)
  local off = {{0, 0}}
  for dx = -4, 4 do
    for dz = -4, 4 do
      if dx ~= 0 or dz ~= 0 then off[#off + 1] = {dx, dz} end
    end
  end
  for i = #off, 2, -1 do
    local j = math.random(i - 1) + 1
    off[i], off[j] = off[j], off[i]
  end
  for k = 1, math.min(#off, 20) do
    local x, z = p.x + off[k][1], p.z + off[k][2]
    local gy = ground_y(x, z)
    if gy then
      local here = {x = x, y = gy, z = z}
      local above = {x = x, y = gy + 1, z = z}
      if not placed[hash(here)] and not placed[hash(above)] then
        local an = minetest.get_node_or_nil(above)
        if an and an.name == "air" then return above end
      end
    end
  end
  return nil
end

minetest.register_globalstep(function(dtime)
  if not running or not rig then return end
  t = t + dtime
  local p = rig:get_pos()
  if not p then return end

  turn = turn + (math.random() - 0.5) * TURN_NOISE * dtime
  turn = turn - turn * TURN_DAMP * dtime
  if turn >  TURN_MAX then turn =  TURN_MAX end
  if turn < -TURN_MAX then turn = -TURN_MAX end
  yaw = yaw + turn * dtime

  if goal and (not placed[goal.key] or t - goal_since > GOAL_GIVEUP) then goal = nil end
  if not goal then
    goal = pick_goal()
    if goal then goal_since = t end
  end
  if goal then
    local gx, gz = goal.rec.pos.x - p.x, goal.rec.pos.z - p.z
    local gd = math.sqrt(gx * gx + gz * gz)
    if gd > VIEW_NEAR then
      local want = math.atan2(-gx / gd, gz / gd)
      yaw = yaw + wrap(want - yaw) * math.min(1, dtime * GOAL_PULL)
    end
  end

  local dxc, dzc = p.x - CX, p.z - CZ
  local rr = math.sqrt(dxc * dxc + dzc * dzc)
  local ahead_ok = ground_y(math.floor(p.x - math.sin(yaw) * 25 + 0.5),
                            math.floor(p.z + math.cos(yaw) * 25 + 0.5)) ~= nil
  if rr > RMAX or not ahead_ok then
    local want = math.atan2(dxc, -dzc)
    local over = math.max(0, rr - RMAX) / 20
    yaw = yaw + wrap(want - yaw) * math.min(1, dtime * PULL * (1 + over))
    turn = turn * 0.5
  end

  local hx, hz = -math.sin(yaw), math.cos(yaw)
  local nx = p.x + hx * SPEED * dtime
  local nz = p.z + hz * SPEED * dtime
  -- HEIGHT above the ground under us, except where a tree is close enough to
  -- fly into, and then only just over it. Taking the clearance everywhere put
  -- the camera ten nodes too high on a treed slope and shrank the blocks.
  local ix, iz = math.floor(nx + 0.5), math.floor(nz + 0.5)
  local g0 = ground_y(ix, iz) or base_y
  local gc = clearance_y(ix, iz) or g0
  local target_y = math.max(g0 + HEIGHT, gc + 4)
  local ny = p.y + (target_y - p.y) * math.min(1, dtime * 1.2)
  rig:set_pos({x = nx, y = ny, z = nz})
  cam_pose.x, cam_pose.y, cam_pose.z, cam_pose.yaw = nx, ny, nz, yaw
  if cam_player then cam_player:set_look_horizontal(yaw) end

  hudacc = hudacc + dtime
  if hudacc > 3 then
    hudacc = 0
    if cam_player then
      cam_player:hud_set_flags(HUD_OFF)
      -- VoxeLibre draws its own hotbar background, which the engine flag does
      -- not touch; the empty slot frame was still on screen in the 600 s smoke
      strip_hud(cam_player)
      cam_player:set_look_vertical(-PITCH)
    end
    clear_sky()
  end

  actacc = actacc + dtime
  if actacc < ACT_EVERY then return end
  actacc = 0

  local d = dir_of(yaw)
  local eye = {x = nx, y = ny + 1.5, z = nz}
  local to  = {x = eye.x + d.x * REACH, y = eye.y + d.y * REACH, z = eye.z + d.z * REACH}
  for hit in minetest.raycast(eye, to, false, false) do
    if hit.type == "node" then
      local np = hit.under
      local node = minetest.get_node(np)
      if node.name ~= "air" and node.name ~= "ignore" and not is_liquid(node.name) then
        local cand = visible_expired(nx, nz, hx, hz)
        if cand then
          minetest.remove_node(cand.pos)
          placed[cand.key] = nil
          if goal and goal.key == cand.key then goal = nil end
          n_redig = n_redig + 1
          ev_count[cand.rec.name] = (ev_count[cand.rec.name] or 0) + 1
          log("redig", cand.rec.name, cand.pos, string.format("%.3f", cand.rec.t))
        elseif #PALETTE > 0 then
          -- Never stack on a block of our own: a tower would change the
          -- skyline and give the census away by silhouette. But doing nothing
          -- in that case throttled the whole capture: once the rig had
          -- carpeted a radius-50 disc the crosshair kept landing on its own
          -- work and the placement rate fell from 0.31 to 0.10 per second, so
          -- the standing set stopped growing at 170 no matter how long the
          -- recording ran. Step aside to free ground instead.
          local ap = free_spot_near(np)
          if ap then
            local put = pick_block(t)
            if pcall(minetest.set_node, ap, {name = put}) then
              placed[hash(ap)] = {name = put, t = t, pos = ap, life = draw_life()}
              n_place = n_place + 1
              log("place", put, ap, "-")
            end
          end
        end
      end
      break
    end
  end
end)

minetest.register_on_shutdown(function()
  log("stop", "-", (rig and rig:get_pos()) or {x=0,y=0,z=0},
      string.format("place=%d redig=%d", n_place, n_redig))
end)

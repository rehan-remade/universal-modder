-- gmod_sandbox.lua: the engine-facing half of the TWAU Garry's Mod sandbox.
-- Runs inside The Wolf Among Us' own Lua 5.1 (numbers are floats). Loaded by TWAU_GMod.asi from
-- <game>\gmod\lua\ and reloaded with the console command `reload`.
--
-- Every function name below exists in TheWolfAmongUs.exe. Argument conventions come from the game's own
-- scripts (dumped at load and listed with the opcode map in MODLOG.md) and from in-game probes; every call
-- still goes through try(), which logs the first failure of each function. A native crash (wrong argument
-- types, e.g. SceneGetCamera() with no scene) is not catchable by pcall: guard arguments before calling.
--
-- C++ natives (registered before this file runs):
--   GMN_Log(msg)
--   GMN_ReportScene(name)
--   GMN_ReportAgent(name, x,y,z, qx,qy,qz,qw, visible, scene)

GM = GM or {}
GM.version = "0.1.0"
GM.agents = GM.agents or {}     -- name -> agent object
GM.frozen = GM.frozen or {}     -- list of {c=controller, t=time, scale=1}
GM.clips = GM.clips or {}       -- handle -> controller
GM.nextClip = GM.nextClip or 1
GM.failed = GM.failed or {}     -- "fn:msg" -> true (log once)
GM.cam = GM.cam      -- kept across `reload` (the camera stays pushed)
GM.light = GM.light

local function log(...)
  local parts = {}
  for i = 1, select("#", ...) do parts[#parts + 1] = tostring(select(i, ...)) end
  GMN_Log(table.concat(parts, " "))
end
GM.log = log

-- Calls a global engine function by name; returns its results, or nil after logging (once) why not.
local function try(fname, ...)
  local f = rawget(_G, fname)
  if type(f) ~= "function" then
    if not GM.failed[fname] then GM.failed[fname] = true; log("[engine] missing", fname) end
    return nil
  end
  local r = { pcall(f, ...) }
  if not r[1] then
    local key = fname .. ":" .. tostring(r[2])
    if not GM.failed[key] then GM.failed[key] = true; log("[engine]", fname, "failed:", r[2]) end
    return nil
  end
  return unpack(r, 2, table.maxn(r))
end
GM.try = try

local function V(x, y, z) return try("Vector", x, y, z) end
-- Quaternions are plain tables here: AgentGetWorldRotQuat returns {x, y, z, w} and AgentSetWorldRotFromQuat
-- takes one. The global Quaternion() is something else (it returned a number in run 7).
local function Q(x, y, z, w) return { x = x, y = y, z = z, w = w } end

-- Telltale vectors/quaternions are userdata with x/y/z(/w) fields; tolerate tables too.
local function xyz(v)
  if v == nil then return nil end
  local ok, x, y, z = pcall(function() return v.x, v.y, v.z end)
  if ok and x then return x, y, z end
  if type(v) == "table" then return v[1], v[2], v[3] end
  return nil
end
local function xyzw(q)
  if q == nil then return nil end
  local ok, x, y, z, w = pcall(function() return q.x, q.y, q.z, q.w end)
  if ok and x then return x, y, z, w end
  if type(q) == "table" then return q[1], q[2], q[3], q[4] end
  return nil
end

local function asList(v)
  if v == nil then return {} end
  if type(v) == "table" then return v end
  return { v }
end

local function agent(name)
  local a = GM.agents[name]
  if a == nil then
    a = try("AgentFind", name)
    GM.agents[name] = a
  end
  return a
end
GM.agent = agent

-- ---------------------------------------------------------------- probing
function GM.Init()
  local need = { "SceneGetActiveSceneNames", "SceneGetAgents", "SceneFind", "SceneGetTimeScale", "SceneSetTimeScale", "AgentGetName", "AgentFind", "AgentGetWorldPos",
    "AgentGetWorldRotQuat", "AgentSetWorldPos", "AgentSetWorldRotFromQuat", "AgentHide", "AgentGetControllers",
    "ControllerSetTimeScale", "ControllerGetTime", "ControllerSetTime", "AgentCreate", "AgentDestroy",
    "CameraPush", "CameraPop", "CameraSetFOV", "PlayAnimationLooping", "ControllerSetContribution",
    "ControllerKill", "SceneOpen", "Vector", "AgentGetForwardVec", "GetFrameTime" }
  local missing = {}
  for _, n in ipairs(need) do
    if type(rawget(_G, n)) ~= "function" then missing[#missing + 1] = n end
  end
  log("[gm] gmod_sandbox.lua " .. GM.version .. " loaded;", #missing == 0 and "all engine functions present"
      or ("missing: " .. table.concat(missing, ", ")))
  return #missing == 0
end

-- ---------------------------------------------------------------- scenes and agents
function GM.ActiveScenes()
  local names = asList(try("SceneGetActiveSceneNames"))
  -- the engine lists each scene once per layer it renders (8x adv_andersenWoodsmanAptNight.scene in run 7)
  local out, seen = {}, {}
  for _, n in pairs(names) do
    if type(n) == "string" and not n:find("^ui_") and not seen[n] then seen[n] = true; out[#out + 1] = n end
  end
  return out
end

-- Reports every agent of the active (non-UI) scenes to C++.
function GM.Snapshot()
  local count = 0
  for _, scene in ipairs(GM.ActiveScenes()) do
    GMN_ReportScene(scene)
    for _, a in pairs(asList(try("SceneGetAgents", scene))) do
      local name = try("AgentGetName", a)
      if name then
        GM.agents[name] = a
        local x, y, z = xyz(try("AgentGetWorldPos", a))
        local qx, qy, qz, qw = xyzw(try("AgentGetWorldRotQuat", a))
        if x then
          local hidden = try("AgentGetProperty", a, "Runtime: Visible")
          -- No mesh list: a logical helper (obj_lookAtBigby, obj_counterStation), nothing to shoot or grab
          local mesh = try("AgentGetProperty", a, "D3D Mesh List") ~= nil
          GMN_ReportAgent(name, x, y, z, qx or 0, qy or 0, qz or 0, qw or 1, hidden ~= false, scene, mesh)
          count = count + 1
        end
      end
    end
  end
  return count
end

function GM.Get(name)
  local a = agent(name)
  if not a then return nil end
  local x, y, z = xyz(try("AgentGetWorldPos", a))
  local qx, qy, qz, qw = xyzw(try("AgentGetWorldRotQuat", a))
  return x, y, z, qx, qy, qz, qw
end

function GM.Set(name, x, y, z, qx, qy, qz, qw)
  local a = agent(name)
  if not a then return false end
  try("AgentSetWorldPos", a, V(x, y, z))
  if qw then try("AgentSetWorldRotFromQuat", a, Q(qx, qy, qz, qw)) end
  return true
end

function GM.Show(name, visible)
  local a = agent(name)
  if not a then return false end
  try("AgentHide", a, not visible)
  return true
end

-- ---------------------------------------------------------------- freezing the story (F1) and resuming (F3)
-- Same as the game's own pause (Game.lua, Pause): every active non-UI scene gets time scale 0 and keeps its
-- old scale for F3, so chores, animations and the dialog line continue from the same frame.
function GM.Freeze()
  GM.frozen = {}
  for _, name in ipairs(GM.ActiveScenes()) do
    local scene = try("SceneFind", name)
    if scene then
      local scale = try("SceneGetTimeScale", scene) or 1
      try("SceneSetTimeScale", scene, 0)
      GM.frozen[#GM.frozen + 1] = { scene = scene, scale = scale }
    end
  end
  -- Our own animations (spawned NPCs) run on a scene that stays live: logic.scene keeps time scale 1
  -- while the story is frozen (run 8), and ControllerSetScene moves a controller onto its clock.
  GM.liveScene = nil
  for _, name in ipairs(asList(try("SceneGetActiveSceneNames", true))) do
    if name == "logic.scene" then GM.liveScene = name end
  end
  try("CursorHide", true)
  -- The game's own UI scenes (hover markers and "Talk To" verbs, inventory, tutorial notifications,
  -- subtitles) keep reacting under our HUD; hide the visible ones and remember which, for F3.
  GM.hiddenUI = {}
  local seen = {}
  for _, name in ipairs(asList(try("SceneGetActiveSceneNames", true))) do
    if not seen[name] and name:find("^ui_") and not try("SceneIsHidden", name) then
      try("SceneHide", name, true)
      GM.hiddenUI[#GM.hiddenUI + 1] = name
    end
    seen[name] = true
  end
  -- The interaction dots (ui_<agent>_dot rings) belong to ReticleSelection.lua, whose update thread runs on
  -- logic.scene and shows them again every frame; its own ref-counted switch keeps them off.
  try("ReticleSelection_ShowNearDots", false, "gm_sandbox")
  try("ReticleSelection_HideDots", true)
  log("[gm] froze", #GM.frozen, "scenes; live clock:", tostring(GM.liveScene), "; hid", #GM.hiddenUI, "UI scenes")
  return #GM.frozen
end

function GM.Unfreeze()
  for _, f in ipairs(GM.frozen) do try("SceneSetTimeScale", f.scene, f.scale) end
  for _, name in ipairs(GM.hiddenUI or {}) do try("SceneHide", name, false) end
  try("ReticleSelection_ShowNearDots", true, "gm_sandbox")
  try("ReticleSelection_HideDots", false)
  log("[gm] resumed", #GM.frozen, "scenes")
  GM.frozen = {}
  GM.hiddenUI = {}
  GM.liveScene = nil
  try("CursorHide", false)
end

-- ---------------------------------------------------------------- first-person camera
function GM.CameraBegin(scene)
  -- SceneGetCamera() without a scene name crashes natively (run 7), which no pcall catches
  if type(scene) ~= "string" or scene == "" then log("[gm] CameraBegin: no scene"); return false end
  GM.prevCam = try("SceneGetCamera", scene)
  -- as the game makes its own cameras (cam_ui_platform_debug in its scripts): rotation nil, two flags false
  GM.cam = try("AgentCreate", "gm_fpcam", "module_camera.prop", V(0, 0, 0), nil, scene, false, false)
  if not GM.cam then return false end
  try("CameraPush", GM.cam)
  return true
end

function GM.CameraSet(x, y, z, qx, qy, qz, qw, fov)
  if not GM.cam then return false end
  try("AgentSetWorldPos", GM.cam, V(x, y, z))
  try("AgentSetWorldRotFromQuat", GM.cam, Q(qx, qy, qz, qw))
  if fov then try("CameraSetFOV", GM.cam, fov) end
  return true
end

-- What the engine thinks the camera's forward is (for axis calibration).
function GM.CameraForward()
  if not GM.cam then return nil end
  return xyz(try("AgentGetForwardVec", GM.cam, true))
end

-- Forward vector of the story camera that was active before ours (to start looking the same way).
function GM.PrevCameraForward()
  if not GM.prevCam then return nil end
  return xyz(try("AgentGetForwardVec", GM.prevCam, true))
end

function GM.Forward(name)
  local a = agent(name)
  if not a then return nil end
  return xyz(try("AgentGetForwardVec", a, true))
end

function GM.CameraEnd()
  if GM.cam then
    try("CameraPop", GM.cam)
    try("AgentDestroy", GM.cam)
  end
  GM.cam = nil
  if GM.prevCam then try("CameraActivate", GM.prevCam) end
end

-- Screen position (0..1) of a world point through the engine's own camera; used to check handedness.
function GM.ScreenPos(x, y, z)
  return xyz(try("CameraGetScreenPosFromWorldPos", V(x, y, z)))
end

-- True if (x, y, z) is on the player's walk boxes. The game asks the same way (Agent.lua):
-- WalkBoxesPosOnWalkBoxes(pos, 0, PathAgentGetWalkBoxes(agent)) returns the nearest point on them.
GM.playerAgent = GM.playerAgent or "Bigby"
local walkBoxes
function GM.OnWalkBoxes(x, y, z)
  local boxes = walkBoxes()
  if not boxes then return true end  -- no walk boxes known: don't block movement
  local px, py, pz = xyz(try("WalkBoxesPosOnWalkBoxes", V(x, y, z), 0, boxes))
  if not px then return true end
  local dx, dz = px - x, pz - z
  return dx * dx + dz * dz < 0.02 * 0.02
end

-- Bigby's walk boxes, else the scene's own (the agent named after the scene carries a "Walk Boxes"
-- property; every path agent in it shares that table). Looked up once per sandbox session.
walkBoxes = function()
  if GM.boxes ~= nil then return GM.boxes or nil end
  local body = agent(GM.playerAgent)
  local boxes = body and try("PathAgentGetWalkBoxes", body)
  if not boxes then
    for _, scene in ipairs(GM.ActiveScenes()) do
      local sa = try("AgentFind", scene)
      boxes = sa and try("AgentGetProperty", sa, "Walk Boxes")
      if boxes then break end
    end
  end
  GM.boxes = boxes or false
  return boxes
end

-- Nearest point on the player's walk boxes; nothing if they're unknown.
function GM.Snap(x, y, z)
  local boxes = walkBoxes()
  if not boxes then return end
  return xyz(try("WalkBoxesPosOnWalkBoxes", V(x, y, z), 0, boxes))
end

-- Where to stand: Bigby's spot (x, y, z) if given, else under the story camera, moved onto the nearest
-- walk box when it is off them (scenes opened from the map menu park Bigby or the camera off the level:
-- adv_fabletownStreetTile105 has Bigby at x 8 and its street at x 397). Returns x, y, z and how it was
-- found ("agent", "under camera", "walkbox", or "camera" when the scene has no walk boxes); nothing when
-- there is no agent, camera or walk box.
function GM.StartPoint(scene, x, y, z)
  GM.boxes = nil
  local how = "agent"
  if not x and type(scene) == "string" and scene ~= "" then
    local cam = try("SceneGetCamera", scene)
    if cam then x, y, z = xyz(try("AgentGetWorldPos", cam)) end
    how = "camera"
  end
  local sx, sy, sz = GM.Snap(x or 0, y or 0, z or 0)
  if not sx then
    if x then return x, y, z, how end
    return
  end
  if x and (sx - x) ^ 2 + (sz - z) ^ 2 < 1.5 * 1.5 then return x, sy, z, how == "camera" and "under camera" or how end
  return sx, sy, sz, "walkbox"
end

-- Walls for bullets: the scene has no raycast against level geometry (AgentAtScreenPos only picks
-- selectable agents, nil on a bare wall), so the walk boxes stand in for it. Marches the ray in `step`
-- metres and returns the distance where it is more than `margin` outside the walk boxes or below floorY;
-- nothing if the ray stays clear for maxDist.
function GM.WallDistance(x, y, z, dx, dy, dz, maxDist, floorY, step, margin)
  local boxes = walkBoxes()
  if not boxes then return end
  -- Shooting from off the walk boxes (noclip): no reference, so no walls.
  local ox, _, oz = xyz(try("WalkBoxesPosOnWalkBoxes", V(x, floorY, z), 0, boxes))
  if not ox or (ox - x) ^ 2 + (oz - z) ^ 2 > margin * margin then return end
  local tFloor
  if dy < -1e-4 then
    tFloor = (floorY - y) / dy
    if tFloor < 0 then tFloor = 0 end
  end
  local limit = maxDist
  if tFloor and tFloor < limit then limit = tFloor end
  local t = 0
  while t < limit do
    t = t + step
    if t > limit then t = limit end
    local px, pz = x + dx * t, z + dz * t
    local qx, _, qz = xyz(try("WalkBoxesPosOnWalkBoxes", V(px, floorY, pz), 0, boxes))
    if not qx then return end
    local ex, ez = qx - px, qz - pz
    if ex * ex + ez * ez > margin * margin then return t end
  end
  if tFloor and tFloor <= maxDist then return tFloor end
end

-- ---------------------------------------------------------------- spawning
function GM.Spawn(name, prop, scene, x, y, z, qx, qy, qz, qw)
  local a = try("AgentCreate", name, prop, V(x, y, z), nil, scene, false, false)
  if not a then return false end
  GM.agents[name] = a
  try("AgentSetSelectable", a, false)  -- no "Talk To" hover and no interaction dot on our spawns
  if qw then try("AgentSetWorldRotFromQuat", a, Q(qx, qy, qz, qw)) end
  return true
end

function GM.Destroy(name)
  local a = GM.agents[name]
  if a then try("AgentDestroy", a) end
  GM.agents[name] = nil
end

-- ---------------------------------------------------------------- animation clips (.anm)
function GM.PlayClip(name, anm, loop, weight, priority)
  local a = agent(name)
  if not a then return -1 end
  local c = loop and try("PlayAnimationLooping", a, anm) or try("PlayAnimation", a, anm)
  if not c then return -1 end
  if GM.liveScene then try("ControllerSetScene", c, GM.liveScene) end
  if priority then try("ControllerSetPriority", c, priority) end
  if weight then try("ControllerSetContribution", c, weight) end
  local h = GM.nextClip
  GM.nextClip = h + 1
  GM.clips[h] = c
  return h
end

function GM.ClipWeight(h, w) local c = GM.clips[h]; if c then try("ControllerSetContribution", c, w) end end
function GM.ClipSpeed(h, s) local c = GM.clips[h]; if c then try("ControllerSetTimeScale", c, s) end end
function GM.ClipPercent(h, p) local c = GM.clips[h]; if c then try("ControllerSetTimePercent", c, p) end end
function GM.StopClip(h)
  local c = GM.clips[h]
  if c then try("ControllerKill", c) end
  GM.clips[h] = nil
end

-- ---------------------------------------------------------------- maps
-- Each episode is a resource set (Fables101..105) and only the running one is enabled, so a scene of
-- another episode can't load its meshes, textures and chores. Turning the running episode's set off crashes
-- the game a moment later (its resources still stream from it), so the target episode is switched on next
-- to it and moved to the front: the same scene name ships in several episodes with different contents.
function GM.UseEpisode(episode)
  if not episode or not episode:find("^Fables10%d$") then return end
  if not try("ResourceSetExists", episode) then log("[gm] no resource set", episode) return end
  local changed = {}
  local extra = try("ContainerToTable", try("SubProject_GetResourceSets", episode))
  for _, set in ipairs({episode, unpack(type(extra) == "table" and extra or {})}) do
    if try("ResourceSetExists", set) and not try("ResourceSetEnabled", set) then
      try("ResourceSetEnable", set)
      changed[#changed + 1] = "+" .. set
    end
  end
  GM.episodePriority = (GM.episodePriority or 1000) + 1  -- the latest choice wins
  local ok, err = pcall(ResourceSetChangePriority, episode, GM.episodePriority)
  log("[gm] resource sets", table.concat(changed, " "), "priority", episode, GM.episodePriority, ok, tostring(err))
end

function GM.OpenScene(scene, episode)
  for _, s in ipairs(GM.ActiveScenes()) do try("SceneRemove", s) end
  GM.agents = {}
  GM.UseEpisode(episode)
  local ok, err = pcall(SceneOpen, scene, "")
  log("[gm] SceneOpen", scene, episode or "", ok, tostring(err))
  return ok
end

-- ---------------------------------------------------------------- flashlight
-- module_light.prop exists in Fables_pc_Project_all; the property names are a guess list until the
-- first in-game run prints which ones exist (GM.Probe("gm_flashlight")).
-- Flashlight. A module_light.prop agent of our own lights nothing (run 16): TWAU lights only reach what is
-- in their light groups. A duplicate of the scene's own character light (light_CHAR_*) does, so that is the
-- template; environment surfaces stay as they are (no scene light reached the floor in the same test).
local function lightTemplate(scene)
  local fallback
  for _, a in pairs(asList(try("SceneGetAgents", scene))) do
    local n = try("AgentGetName", a)
    if n and n:sub(1, 3) ~= "gm_" and try("AgentGetProperty", a, "Light Turned On") ~= nil then
      if n:find("^light_CHAR") then return a, n end
      fallback = fallback or a
    end
  end
  return fallback
end

function GM.Light(on, scene, x, y, z, qx, qy, qz, qw)
  if not on then
    if GM.light then try("AgentDestroy", GM.light) end
    GM.light = nil
    return true
  end
  if not GM.light then
    local tpl, tplName = lightTemplate(scene)
    if tpl then GM.light = try("AgentDuplicate", "gm_flashlight", tpl) end
    if not GM.light then
      GM.light = try("AgentCreate", "gm_flashlight", "module_light.prop", V(x, y, z), nil, scene, false, false)
    end
    if not GM.light then return false end
    try("AgentSetProperty", GM.light, "Light Turned On", true)
    try("AgentSetProperty", GM.light, "Light Intensity", 1.6)
    log("[gm] flashlight from", tostring(tplName or "module_light.prop"))
  end
  try("AgentSetWorldPos", GM.light, V(x, y, z))
  try("AgentSetWorldRotFromQuat", GM.light, Q(qx, qy, qz, qw))
  return true
end

-- ---------------------------------------------------------------- debugging from the console
function GM.Probe(name)
  local a = agent(name or "Bigby")
  log("[probe]", name, "agent:", tostring(a), type(a))
  if not a then return end
  log("[probe] pos", xyz(try("AgentGetWorldPos", a)))
  log("[probe] quat", xyzw(try("AgentGetWorldRotQuat", a)))
  log("[probe] fwd", xyz(try("AgentGetForwardVec", a, true)))
  local props = try("AgentGetRuntimeProperties", a)
  log("[probe] runtime props", tostring(props))
  local keys = try("PropertyGetKeys", props)
  if type(keys) == "table" then for _, k in pairs(keys) do log("[probe]  key", k) end end
  for _, c in pairs(asList(try("AgentGetControllers", a))) do
    log("[probe] controller", tostring(c), "t=", try("ControllerGetTime", c), "len=", try("ControllerGetLength", c))
  end
end

return GM.Init()

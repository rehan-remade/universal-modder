// ModLab: a deliberately controlled SINGLE-PLAYER laboratory.
// The two lanes use the real Mindustry turret / bullet / collision engine.
// The moving target is scripted, and both turrets aim at a fixed marker.
// This demonstrates steering; it is not a normal-play DPS benchmark.
var active = false;
var clock = 0;
var targets = [];
var turrets = [];
var shots = [0, 0];
var hits = [0, 0];
var centers = [176, 464];
var hud = null;
var statusLabel = null;
var limit = 60 * 30;
var done = false;
var modId = 'modlab-homing';
var previousMinZoom = null;
var previousScale = null;

function laneFor(bullet){
  if(!bullet || !bullet.owner) return -1;
  for(var i = 0; i < turrets.length; i++) if(bullet.owner.id === turrets[i].id) return i;
  return -1;
}

function spawnTarget(i){
  var u = UnitTypes.flare.create(Team.crux);
  u.set(centers[i], 304);
  u.health = 10000;
  u.add();
  u.controller(extend(AIController, { updateUnit: function(){} }));
  targets[i] = u;
}

function recordResult(){
  var result = {
    game: 'Mindustry', build: String(Version.build) + '.' + String(Version.revision), modVersion: '0.1.0',
    simulationTicks: clock, durationSeconds: clock / 60,
    method: 'real desktop engine; scripted identical targets; fixed aim; no splash; steering demonstration, not a normal-play benchmark',
    shots: shots, hits: hits, finished: done,
    observer: String(Vars.player.unit().type), observerDead: Vars.player.dead()
  };
  Vars.dataDirectory.child('modlab-last-run.json').writeString(JSON.stringify(result, null, 2));
}

function startLab(){
  if(Vars.net.active()){
    Vars.ui.showInfo('This lab is single-player only. Disconnect first.');
    return;
  }
  if(!Vars.state.isMenu() && !active){
    Vars.ui.showInfo('Return to the main menu before opening the lab. Save your current game first.');
    return;
  }
  if(hud !== null){hud.remove(); hud = null;}
  active = false;
  Vars.logic.reset();
  var rules = new Rules();
  rules.infiniteResources = true;
  rules.teams.get(Team.sharded).cheat = true;
  rules.waves = false;
  rules.canGameOver = false;
  rules.enemyCoreBuildRadius = 0;
  rules.unitCap = 30;
  Vars.state.rules = rules;
  Vars.world.loadGenerator(80, 62, cons(function(tiles){
    tiles.fill();
    for(var x = 0; x < 80; x++){
      for(var y = 0; y < 62; y++){
        var tile = tiles.getn(x,y);
        tile.setFloor((x === 40 || y === 8 || y === 49) ? Blocks.darkPanel3 : Blocks.stone);
      }
    }
    tiles.getn(5,5).setBlock(Blocks.coreShard, Team.sharded, 0);
    tiles.getn(22,14).setBlock(Vars.content.block(modId + '-baseline'), Team.sharded, 0);
    tiles.getn(58,14).setBlock(Vars.content.block(modId + '-homing'), Team.sharded, 0);
  }));
  Vars.player.team(Team.sharded);
  Vars.logic.play();
  Vars.player.set(320, 248);
  var observer = UnitTypes.alpha.create(Team.sharded);
  observer.set(320, 248);
  observer.add();
  Vars.player.unit(observer);
  if(previousMinZoom === null){
    previousMinZoom = Vars.renderer.minZoom;
    previousScale = Vars.renderer.getScale();
  }
  Vars.renderer.minZoom = 0.5;
  Vars.renderer.minZoomInGame = 0.5;
  Vars.renderer.setScale(Math.min(Core.graphics.getWidth()/720, Core.graphics.getHeight()/600));
  Core.camera.position.set(320,248);
  turrets = [Vars.world.build(22,14), Vars.world.build(58,14)];
  targets = [];
  shots = [0,0]; hits = [0,0]; clock = 0; done = false;
  spawnTarget(0); spawnTarget(1);
  active = true;
  hud = new Table();
  hud.setFillParent(true);
  hud.top().marginTop(8);
  hud.table(Styles.black6, cons(function(t){
    t.defaults().pad(5);
    t.add('[accent]MODLAB / HOMING LAB[]').colspan(3).get().setFontScale(0.8); t.row();
    t.add('LEFT: straight     |     RIGHT: homing').colspan(3).get().setFontScale(0.7); t.row();
    statusLabel = t.add('Running a 30-second steering comparison...').colspan(3).get();
    statusLabel.setFontScale(0.7);
    t.row();
    t.button('Restart [F8]', run(startLab)).width(160);
    t.button('Exit lab [F9]', run(exitLab)).width(160);
    t.row();
    t.add('[lightgray]Identical targets / Fixed aim / Real engine[]').colspan(3).get().setFontScale(0.65);
  }));
  Core.scene.add(hud);
  print('LAB_START: desktop steering comparison');
}

function exitLab(){
  if(!active) return;
  recordResult();
  active = false;
  if(hud !== null){hud.remove();hud = null;}
  if(previousMinZoom !== null){
    Vars.renderer.minZoom = previousMinZoom;
    Vars.renderer.setScale(previousScale);
    previousMinZoom = null;
  }
  Vars.state.set(GameState.State.menu);
  Vars.logic.reset();
}

Events.on(ClientLoadEvent, cons(function(){
  Vars.ui.menufrag.addButton('ModLab Homing Lab [F8]', run(startLab));
  Events.fire(new ResizeEvent());
  print('READY: ModLab Homing Lab 0.1.0. F8 opens a local laboratory from the main menu.');
}));

Events.on(UnitDamageEvent, cons(function(e){
  if(!active || done) return;
  var i = laneFor(e.bullet);
  if(i >= 0 && e.unit.id === targets[i].id) hits[i]++;
}));
Events.run(Trigger.update, run(function(){
  if(Vars.headless) return;
  if(Core.input.keyTap(KeyCode.f8)) startLab();
  if(Core.input.keyTap(KeyCode.f9)) exitLab();
  if(!active) return;
  if(Vars.net.active() || Vars.state.isMenu()){
    active = false;
    if(hud !== null){hud.remove();hud = null;}
    return;
  }
  if(Vars.state.isPaused()) return;
  if(!done) clock += Time.delta;
  var motion = clock / 68;
  for(var i=0;i<2;i++){
    if(!targets[i].isAdded()) spawnTarget(i);
    targets[i].set(centers[i] + 72 * Math.sin(motion), 304 + 18 * Math.cos(motion));
    targets[i].rotation = Math.cos(motion) >= 0 ? 0 : 180;
    targets[i].health = 10000;
    targets[i].isShooting = false;
    for(var m=0;m<targets[i].mounts.length;m++) targets[i].mounts[m].shoot = false;
    shots[i] = turrets[i].totalShots;
    if(turrets[i].totalAmmo < 4) turrets[i].handleStack(Items.copper, 10, null);
    turrets[i].control(LAccess.shoot, centers[i]/8, 304/8, done ? 0 : 1, 0);
  }
  if(!done && clock >= limit){done = true;recordResult();print('LAB_FINISH: ' + JSON.stringify({shots:shots,hits:hits}));}
  statusLabel.setText((done ? '[accent]Finished[]' : (clock/60).toFixed(1) + ' / 30s') + '  |  straight ' + hits[0] + '/' + shots[0] + ' hits  |  homing ' + hits[1] + '/' + shots[1] + ' hits');
}));

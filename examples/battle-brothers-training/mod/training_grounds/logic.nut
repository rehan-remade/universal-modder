// Pure arithmetic, no game objects. Runs under a plain Squirrel interpreter (see tests/).
// Attribute index order matches vanilla ::Const.Attributes.
::TG.Penalty <- 0.75;      // -25 per cent on every attribute while training
::TG.PreRolledLevels <- 10; // vanilla pre-rolls this many level-up gains; later level-ups give +1

::TG.Stats <- [
	{ Idx = 0, Key = "Hitpoints",    Name = "Hitpoints",     Icon = "ui/icons/health.png" },
	{ Idx = 1, Key = "Bravery",      Name = "Resolve",       Icon = "ui/icons/bravery.png" },
	{ Idx = 2, Key = "Stamina",      Name = "Fatigue",       Icon = "ui/icons/fatigue.png" },
	{ Idx = 3, Key = "Initiative",   Name = "Initiative",    Icon = "ui/icons/initiative.png" },
	{ Idx = 4, Key = "MeleeSkill",   Name = "Melee Skill",   Icon = "ui/icons/melee_skill.png" },
	{ Idx = 5, Key = "RangedSkill",  Name = "Ranged Skill",  Icon = "ui/icons/ranged_skill.png" },
	{ Idx = 6, Key = "MeleeDefense", Name = "Melee Defense", Icon = "ui/icons/melee_defense.png" },
	{ Idx = 7, Key = "RangedDefense",Name = "Ranged Defense",Icon = "ui/icons/ranged_defense.png" }
];

// Vanilla ::Const.AttributesLevelUp as [min, max] per attribute index. Replaced from the game at runtime.
::TG.LevelUp <- [[2, 4], [2, 4], [2, 4], [3, 5], [1, 3], [2, 4], [1, 3], [2, 4]];

// Vanilla character_background.buildAttributes() default start ranges, by stat key.
::TG.DefaultRange <- {
	Hitpoints = [50, 60], Bravery = [30, 40], Stamina = [90, 100], MeleeSkill = [47, 57],
	RangedSkill = [32, 42], MeleeDefense = [0, 5], RangedDefense = [0, 5], Initiative = [100, 110]
};

::TG.Logic <- {
	function min( _a, _b ) { return _a < _b ? _a : _b; }
	function max( _a, _b ) { return _a > _b ? _a : _b; }
	function clamp( _v, _lo, _hi ) { return _v < _lo ? _lo : (_v > _hi ? _hi : _v); }
	function round( _f ) { return (_f + 0.5).tointeger(); }

	// Level-ups whose stat gains were already applied to the base value.
	function appliedLevelUps( _level, _pending )
	{
		return this.max(0, _level - 1 - _pending);
	}

	// Min / max / expected total gain from _n applied level-ups for one attribute.
	// Vanilla: first PreRolledLevels gains are rolled in [Min + talent', Max + (talent == 3 ? 1 : 0)]
	// with talent' = 2 when talent == 3; later level-ups give exactly 1.
	function gainRange( _idx, _n, _talent, _levelUp )
	{
		local rolled = this.min(_n, ::TG.PreRolledLevels);
		local extra = _n - rolled;
		local lo = _levelUp[_idx][0] + (_talent == 3 ? 2 : _talent);
		local hi = _levelUp[_idx][1] + (_talent == 3 ? 1 : 0);
		return {
			min = lo * rolled + extra,
			max = hi * rolled + extra,
			exp = (lo + hi) / 2.0 * rolled + extra
		};
	}

	// Best guess of the starting roll. Vanilla keeps no record of it, so it is the current base
	// value minus the expected level gains, forced into the range that is still possible.
	function estimateStart( _base, _n, _talent, _idx, _bgMin, _bgMax, _levelUp )
	{
		local g = this.gainRange(_idx, _n, _talent, _levelUp);
		local lo = this.max(_bgMin, _base - g.max);
		local hi = this.min(_bgMax, _base - g.min);
		local est = _base - g.exp;
		if (lo > hi)
		{
			lo = _bgMin;
			hi = _bgMax;
		}
		return this.round(this.clamp(est, lo, hi));
	}

	// How much the base value rises when the start roll is lifted to the background maximum.
	function delta( _base, _n, _talent, _idx, _bgMin, _bgMax, _levelUp )
	{
		return this.max(0, _bgMax - this.estimateStart(_base, _n, _talent, _idx, _bgMin, _bgMax, _levelUp));
	}

	// Stable per-town lottery: the same town name always gives the same answer, so a town keeps or
	// never gets the building across saves and restarts. _percent is the share of towns that have it.
	function townHasBuilding( _name, _percent )
	{
		local h = 7;
		for (local i = 0; i < _name.len(); i++)
			h = (h * 31 + _name[i]) % 1000003;
		return (h % 100) < _percent;
	}

	function cost( _level, _base, _perLevel )
	{
		return this.max(0, _base + _perLevel * _level);
	}
};

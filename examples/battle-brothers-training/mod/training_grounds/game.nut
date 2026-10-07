// Helpers that touch game objects. Loaded after MSU is ready.
::TG.getSetting <- function( _id, _default )
{
	try
	{
		if (::TG.Mod != null)
			return ::TG.Mod.ModSettings.getSetting(_id).getValue();
	}
	catch (err)
	{
		::logWarning("Training Grounds: setting " + _id + " unavailable, using default");
	}
	return _default;
};

::TG.getDays <- function() { return ::TG.getSetting("Days", 5); };

::TG.getCost <- function( _bro )
{
	return ::TG.Logic.cost(_bro.getLevel(), ::TG.getSetting("CostBase", 500), ::TG.getSetting("CostPerLevel", 150));
};

if ("AttributesLevelUp" in ::Const)
{
	::TG.LevelUp = [];
	foreach (e in ::Const.AttributesLevelUp)
		::TG.LevelUp.push([e.Min, e.Max]);
}

// Start-roll range of the brother's background for one stat key. Mirrors
// character_background.buildAttributes(): defaults plus onChangeAttributes().
::TG.getStartRange <- function( _bro, _key )
{
	local r = ::TG.DefaultRange[_key];
	local c = _bro.getBackground().onChangeAttributes();
	if (_key in c)
		return [r[0] + c[_key][0], r[1] + c[_key][1]];
	return [r[0], r[1]];
}

// One entry per stat: base value now, estimated start roll, gain from maxing it.
::TG.getStatInfo <- function( _bro )
{
	local props = _bro.getBaseProperties();
	local n = ::TG.Logic.appliedLevelUps(_bro.getLevel(), _bro.m.LevelUps);
	local out = [];
	foreach (s in ::TG.Stats)
	{
		local range = ::TG.getStartRange(_bro, s.Key);
		local talent = 0;
		if (_bro.m.Talents.len() > s.Idx)
			talent = _bro.m.Talents[s.Idx];
		local d = 0;
		if (!_bro.getFlags().has("tg_max_" + s.Key))
			d = ::TG.Logic.delta(props[s.Key], n, talent, s.Idx, range[0], range[1], ::TG.LevelUp);
		out.push({ Stat = s, Base = props[s.Key], BgMax = range[1], Delta = d });
	}
	return out;
}

::TG.isTraining <- function( _bro )
{
	return _bro.getSkills().hasSkill("effects.tg_training");
}

// The building lives outside settlement.m.Buildings (never serialized, so no save dependency).
// It occupies the first free slot, skipping slot 3 in coastal towns (vanilla puts the port there).
::TG.getFreeSlot <- function( _settlement )
{
	if (!::TG.Logic.townHasBuilding(_settlement.getName(), ::TG.getSetting("TownPercent", 25)))
		return null;
	for (local i = 0; i < _settlement.m.Buildings.len(); i++)
	{
		if (i == 3 && _settlement.m.IsCoastal)
			continue;
		if (_settlement.m.Buildings[i] == null)
			return i;
	}
	return null;
}

::TG.getBuilding <- function( _settlement )
{
	local b = ::new("scripts/entity/world/settlements/buildings/tg_training_grounds_building");
	b.setSettlement(_settlement);
	return b;
}

::TG.openWizard <- function( _settlement )
{
	if (::World.Events.hasActiveEvent())
		return;
	local ev = ::new("scripts/mods/tg/tg_wizard_event");
	ev.m.Town = _settlement;
	ev.fire();
	::World.Events.m.ActiveEvent = ev;
	::World.State.showEventScreenFromTown(ev);
}

::TG.join <- function( _array )
{
	local s = "";
	foreach (i, v in _array)
		s += (i > 0 ? ", " : "") + v;
	return s;
}

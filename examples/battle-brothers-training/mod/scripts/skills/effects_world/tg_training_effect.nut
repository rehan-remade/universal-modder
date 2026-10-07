// Holds the whole training state on the brother (days left + chosen stats), so it is saved with him
// and disappears with him if he dies or is dismissed.
this.tg_training_effect <- this.inherit("scripts/skills/skill", {
	m = {
		DaysLeft = 5,
		Stats = []
	},
	function create()
	{
		this.m.ID = "effects.tg_training";
		this.m.Name = "Hard Training";
		this.m.Description = "Pushed to the limit at the training grounds. Worn out for now, but the work will pay off.";
		this.m.Icon = "skills/status_effect_62.png";
		this.m.Type = this.m.Type | this.Const.SkillType.StatusEffect;
	}

	function getTooltip()
	{
		local names = "";
		foreach (i in this.m.Stats)
		{
			names += (names.len() > 0 ? ", " : "") + ::TG.Stats[i].Name;
		}
		return [
			{ id = 1, type = "title", text = this.getName() },
			{ id = 2, type = "description", text = this.getDescription() },
			{ id = 10, type = "text", icon = "ui/icons/special.png", text = "[color=" + this.Const.UI.Color.NegativeValue + "]-25%[/color] to all attributes" },
			{ id = 11, type = "text", icon = "ui/icons/special.png", text = "Will improve: " + names },
			{ id = 12, type = "hint", icon = "ui/icons/action_points.png", text = "Done in " + this.m.DaysLeft + " more day(s)" }
		];
	}

	function onUpdate( _properties )
	{
		_properties.HitpointsMult *= ::TG.Penalty;
		_properties.BraveryMult *= ::TG.Penalty;
		_properties.StaminaMult *= ::TG.Penalty;
		_properties.InitiativeMult *= ::TG.Penalty;
		_properties.MeleeSkillMult *= ::TG.Penalty;
		_properties.RangedSkillMult *= ::TG.Penalty;
		_properties.MeleeDefenseMult *= ::TG.Penalty;
		_properties.RangedDefenseMult *= ::TG.Penalty;
	}

	function onNewDay()
	{
		--this.m.DaysLeft;
		if (this.m.DaysLeft <= 0)
		{
			this.complete();
		}
	}

	function complete()
	{
		local actor = this.getContainer().getActor();
		local info = ::TG.getStatInfo(actor);
		local props = actor.getBaseProperties();
		local gains = [];
		foreach (i in this.m.Stats)
		{
			local e = info[i];
			if (e.Delta > 0)
			{
				props[e.Stat.Key] += e.Delta;
				if (e.Stat.Key == "Hitpoints")
					actor.setHitpoints(actor.getHitpoints() + e.Delta);
				gains.push(e.Stat.Name + " +" + e.Delta);
			}
			actor.getFlags().set("tg_max_" + e.Stat.Key, true);
		}
		this.logInfo(this.Const.UI.getColorizedEntityName(actor) + " finished hard training: " + (gains.len() > 0 ? ::TG.join(gains) : "no gain"));
		this.removeSelf();
	}

	function onSerialize( _out )
	{
		this.skill.onSerialize(_out);
		_out.writeU8(this.m.DaysLeft);
		_out.writeU8(this.m.Stats.len());
		foreach (i in this.m.Stats)
			_out.writeU8(i);
	}

	function onDeserialize( _in )
	{
		this.skill.onDeserialize(_in);
		this.m.DaysLeft = _in.readU8();
		local n = _in.readU8();
		this.m.Stats = [];
		for (local k = 0; k < n; k++)
			this.m.Stats.push(_in.readU8());
	}
});

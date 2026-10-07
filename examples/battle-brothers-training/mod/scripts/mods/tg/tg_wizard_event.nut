// Dialog wizard built on the vanilla event screen: pick a brother, pick stats, confirm.
// Screens are built on the fly; getResult returns the next screen table (event.getScreen accepts tables).
this.tg_wizard_event <- this.inherit("scripts/events/event", {
	m = {
		Town = null,
		Brother = null,
		Picked = [],
		Page = 0
	},
	function create()
	{
		this.m.ID = "event.tg_wizard";
		this.m.Title = "Training Grounds";
		this.m.IsSpecial = true;
	}

	function onDetermineStartScreen()
	{
		return this.brotherScreen();
	}

	function opt( _text, _fn )
	{
		return { Text = _text, getResult = _fn };
	}

	function makeScreen( _text, _options )
	{
		return {
			ID = "TG",
			Text = _text,
			Image = "",
			List = [],
			Characters = [],
			Options = _options,
			function start( _event )
			{
				if (_event.m.Brother != null)
					this.Characters.push(_event.m.Brother.getImagePath());
			}
		};
	}

	function leaveOpt()
	{
		return this.opt("Leave", function ( _event ) { return 0; });
	}

	function brotherScreen()
	{
		this.m.Brother = null;
		this.m.Picked = [];
		local perPage = 6;
		local list = [];
		foreach (b in this.World.getPlayerRoster().getAll())
		{
			if (!::TG.isTraining(b))
				list.push(b);
		}
		local pages = this.Math.max(1, (list.len() + perPage - 1) / perPage);
		if (this.m.Page >= pages)
			this.m.Page = 0;
		local options = [];
		local from = this.m.Page * perPage;
		for (local i = from; i < list.len() && i < from + perPage; i++)
			options.push(this.brotherOption(list[i]));
		if (pages > 1)
		{
			options.push(this.opt("More brothers (" + (this.m.Page + 1) + "/" + pages + ")", function ( _event ) {
				_event.m.Page++;
				return _event.brotherScreen();
			}));
		}
		options.push(this.leaveOpt());
		local text = "The drill master offers to push one of your men to his limit. For " + ::TG.getDays() + " days the man will be worn down (25 per cent penalty to every attribute), then three attributes of your choice are lifted to the best start his background allows. Level-up gains are kept.\n\nWho will it be?";
		return this.makeScreen(text, options);
	}

	function brotherOption( _bro )
	{
		local cost = ::TG.getCost(_bro);
		local afford = this.World.Assets.getMoney() >= cost;
		local label = _bro.getName() + ", level " + _bro.getLevel() + " - " + cost + " crowns" + (afford ? "" : " (too expensive)");
		return this.opt(label, function ( _event ) {
			if (!afford || ::World.Assets.getMoney() < cost)
				return _event.brotherScreen();
			_event.m.Brother = _bro;
			_event.m.Picked = [];
			return _event.statScreen();
		});
	}

	function statScreen()
	{
		local info = ::TG.getStatInfo(this.m.Brother);
		local open = [];
		foreach (e in info)
		{
			if (e.Delta > 0)
				open.push(e);
		}
		local need = this.Math.min(3, open.len());
		if (need == 0 || this.m.Picked.len() >= need)
			return this.confirmScreen();
		local options = [];
		foreach (e in open)
		{
			if (this.m.Picked.find(e.Stat.Idx) != null)
				continue;
			options.push(this.statOption(e));
		}
		options.push(this.opt("Pick another brother", function ( _event ) { return _event.brotherScreen(); }));
		local text = "Choose " + (need - this.m.Picked.len()) + " more attribute(s) for " + this.m.Brother.getName() + ". Gains are estimates: the game keeps no record of his original roll.";
		return this.makeScreen(text, options);
	}

	function statOption( _e )
	{
		local label = _e.Stat.Name + " (now " + _e.Base + ", about +" + _e.Delta + ")";
		local idx = _e.Stat.Idx;
		return this.opt(label, function ( _event ) {
			_event.m.Picked.push(idx);
			return _event.statScreen();
		});
	}

	function confirmScreen()
	{
		local cost = ::TG.getCost(this.m.Brother);
		local info = ::TG.getStatInfo(this.m.Brother);
		local names = [];
		foreach (i in this.m.Picked)
			names.push(info[i].Stat.Name + " (about +" + info[i].Delta + ")");
		local text = this.m.Brother.getName() + " will train for " + ::TG.getDays() + " days at a cost of " + cost + " crowns.\n\nImproves: " + (names.len() > 0 ? ::TG.join(names) : "nothing, he is already at the limit") + ".";
		local options = [];
		if (names.len() > 0)
			options.push(this.opt("Begin training", function ( _event ) { return _event.begin(); }));
		options.push(this.opt("Choose again", function ( _event ) {
			_event.m.Picked = [];
			return _event.statScreen();
		}));
		options.push(this.leaveOpt());
		return this.makeScreen(text, options);
	}

	function begin()
	{
		local bro = this.m.Brother;
		local cost = ::TG.getCost(bro);
		if (this.World.Assets.getMoney() < cost || ::TG.isTraining(bro))
			return this.brotherScreen();
		this.World.Assets.addMoney(-cost);
		local effect = this.new("scripts/skills/effects_world/tg_training_effect");
		effect.m.DaysLeft = ::TG.getDays();
		effect.m.Stats = clone this.m.Picked;
		bro.getSkills().add(effect);
		this.logInfo(this.Const.UI.getColorizedEntityName(bro) + " begins hard training for " + effect.m.DaysLeft + " days.");
		return this.makeScreen(bro.getName() + " heads to the yard. You pay " + cost + " crowns.", [this.leaveOpt()]);
	}
});

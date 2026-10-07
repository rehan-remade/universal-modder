// Dialog wizard built on the vanilla event screen: pick a brother, pick stats, confirm.
// Screens are built on the fly. Vanilla processInput only accepts a screen ID (string) or 0 from a button,
// so makeScreen stores the new screen in m.Screens under a fresh ID and returns that ID.
this.tg_wizard_event <- this.inherit("scripts/events/event", {
	m = {
		Town = null,
		Brother = null,
		Picked = [],
		Page = 0,
		Counter = 0,
		StatPage = 0
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

	// _chars: portrait image paths, _rows: List entries ({ id, icon, text }). Both are filled in start(),
	// because setScreen() clears Characters and List and then calls start (vanilla training_accident_event does the same).
	function makeScreen( _text, _options, _chars = null, _rows = null )
	{
		this.m.Counter++;
		local id = "TG" + this.m.Counter;
		this.m.Screens = [{
			ID = id,
			Text = _text,
			Image = "",
			List = [],
			Characters = [],
			Chars = _chars == null ? [] : _chars,
			Rows = _rows == null ? [] : _rows,
			Options = _options,
			function start( _event )
			{
				foreach (p in this.Chars)
					this.Characters.push(p);
				foreach (r in this.Rows)
					this.List.push(r);
			}
		}];
		return id;
	}

	function row( _icon, _text, _color = null )
	{
		this.m.Counter++;
		local t = _color == null ? _text : "[color=" + _color + "]" + _text + "[/color]";
		return { id = 10 + this.m.Counter, icon = _icon, text = t };
	}


	function leaveOpt()
	{
		return this.opt("Leave", function ( _event ) { return 0; });
	}

	function brotherScreen()
	{
		this.m.Brother = null;
		this.m.Picked = [];
		this.m.StatPage = 0;
		local perPage = 3;
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
		local chars = [];
		local rows = [];
		local money = this.World.Assets.getMoney();
		local from = this.m.Page * perPage;
		for (local i = from; i < list.len() && i < from + perPage; i++)
		{
			local b = list[i];
			local cost = ::TG.getCost(b);
			options.push(this.brotherOption(b));
			chars.push(b.getImagePath());
			local line = b.getName() + ", level " + b.getLevel() + " " + b.getBackground().getNameOnly() + ": " + cost + " crowns";
			if (money >= cost)
				rows.push(this.row("ui/icons/asset_money.png", line));
			else
				rows.push(this.row("ui/icons/asset_money.png", line + " (too expensive)", this.Const.UI.Color.NegativeEventValue));
		}
		if (pages > 1)
		{
			options.push(this.opt("More brothers (" + (this.m.Page + 1) + "/" + pages + ")", function ( _event ) {
				_event.m.Page++;
				return _event.brotherScreen();
			}));
		}
		options.push(this.leaveOpt());
		local text = ::TG.pick(::TG.Lines.Intro) + "\n\nFor " + ::TG.getDays() + " days the man will be worn down (25 per cent penalty to every attribute). Then three attributes of your choice are lifted to the best start his background allows. Level-up gains are kept.\n\nWho will it be?";
		return this.makeScreen(text, options, chars, rows);
	}

	function brotherOption( _bro )
	{
		local cost = ::TG.getCost(_bro);
		local afford = this.World.Assets.getMoney() >= cost;
		local label = _bro.getName() + (afford ? "" : " (too expensive)");
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
		local left = [];
		foreach (e in open)
		{
			if (this.m.Picked.find(e.Stat.Idx) == null)
				left.push(e);
		}
		local perPage = 3;
		local pages = this.Math.max(1, (left.len() + perPage - 1) / perPage);
		if (this.m.StatPage >= pages)
			this.m.StatPage = 0;
		local options = [];
		local from = this.m.StatPage * perPage;
		for (local i = from; i < left.len() && i < from + perPage; i++)
			options.push(this.statOption(left[i]));
		if (pages > 1)
		{
			options.push(this.opt("More attributes (" + (this.m.StatPage + 1) + "/" + pages + ")", function ( _event ) {
				_event.m.StatPage++;
				return _event.statScreen();
			}));
		}
		options.push(this.opt("Pick another brother", function ( _event ) { return _event.brotherScreen(); }));
		local rows = [];
		foreach (e in info)
		{
			local nm = e.Stat.Name + " " + e.Base;
			if (this.m.Picked.find(e.Stat.Idx) != null)
				rows.push(this.row(e.Stat.Icon, nm + " to about " + (e.Base + e.Delta) + " (chosen)", this.Const.UI.Color.PositiveEventValue));
			else if (e.Delta > 0)
				rows.push(this.row(e.Stat.Icon, nm + ", about +" + e.Delta));
			else
				rows.push(this.row(e.Stat.Icon, nm + ", nothing left to gain"));
		}
		local text = ::TG.pick(::TG.Lines.Stats) + "\n\nChoose " + (need - this.m.Picked.len()) + " more attribute(s) for " + this.m.Brother.getName() + ". Gains are estimates: the game keeps no record of his original roll.";
		return this.makeScreen(text, options, [this.m.Brother.getImagePath()], rows);
	}

	function statOption( _e )
	{
		local label = _e.Stat.Name + " (now " + _e.Base + ", about +" + _e.Delta + ")";
		local idx = _e.Stat.Idx;
		return this.opt(label, function ( _event ) {
			_event.m.Picked.push(idx);
			_event.m.StatPage = 0;
			return _event.statScreen();
		});
	}

	function confirmScreen()
	{
		local cost = ::TG.getCost(this.m.Brother);
		local info = ::TG.getStatInfo(this.m.Brother);
		local rows = [];
		foreach (i in this.m.Picked)
		{
			local e = info[i];
			rows.push(this.row(e.Stat.Icon, e.Stat.Name + " " + e.Base + " to about " + (e.Base + e.Delta), this.Const.UI.Color.PositiveEventValue));
		}
		rows.push(this.row("ui/icons/asset_money.png", "Cost: " + cost + " crowns", this.Const.UI.Color.NegativeEventValue));
		rows.push(this.row("ui/icons/days_wounded.png", "Training takes " + ::TG.getDays() + " days"));
		rows.push(this.row("ui/icons/warning.png", "-25% to all attributes until then", this.Const.UI.Color.NegativeEventValue));
		local text = this.m.Brother.getName() + " will train for " + ::TG.getDays() + " days at a cost of " + cost + " crowns.";
		if (this.m.Picked.len() == 0)
			text += "\n\nHe is already at the limit of what his background allows, so there is nothing to gain.";
		else
			text += "\n\n" + ::TG.pick(::TG.Lines.Confirm);
		local options = [];
		if (this.m.Picked.len() > 0)
			options.push(this.opt("Begin training", function ( _event ) { return _event.begin(); }));
		options.push(this.opt("Choose again", function ( _event ) {
			_event.m.Picked = [];
			return _event.statScreen();
		}));
		options.push(this.leaveOpt());
		return this.makeScreen(text, options, [this.m.Brother.getImagePath()], rows);
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
		local rows = [
			this.row("ui/icons/asset_money.png", "You pay " + cost + " crowns", this.Const.UI.Color.NegativeEventValue),
			this.row("ui/icons/days_wounded.png", bro.getName() + " is back in " + effect.m.DaysLeft + " days")
		];
		return this.makeScreen(bro.getName() + " heads to the yard. " + ::TG.pick(::TG.Lines.Begin), [this.leaveOpt()], [bro.getImagePath()], rows);
	}
});

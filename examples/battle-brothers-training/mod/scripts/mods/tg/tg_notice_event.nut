// One-screen notice shown on the world map when a brother finishes training. Built like a vanilla event
// (Characters + List filled in start), fired by ::TG.showNotice from the event manager hook.
this.tg_notice_event <- this.inherit("scripts/events/event", {
	m = {
		Name = "",
		Image = "",
		Lines = [],
		Body = ""
	},
	function create()
	{
		this.m.ID = "event.tg_notice";
		this.m.Title = "Training Grounds";
		this.m.IsSpecial = true;
	}

	function onDetermineStartScreen()
	{
		this.m.Screens = [{
			ID = "A",
			Text = this.m.Body,
			Image = "",
			List = [],
			Characters = [],
			Options = [{
				Text = "Good.",
				function getResult( _event ) { return 0; }
			}],
			function start( _event )
			{
				this.Characters.push(_event.m.Image);
				local n = 10;
				foreach (l in _event.m.Lines)
				{
					this.List.push({ id = n, icon = l.Icon, text = l.Text });
					n++;
				}
			}
		}];
		return "A";
	}
});

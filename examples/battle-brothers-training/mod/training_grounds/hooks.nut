// Vanilla hooks (Modern Hooks API).
::TG.HooksMod.hook("scripts/entity/world/settlement", function( q ) {
	// Add our building to the slot list sent to the town screen.
	q.getUIInformation = @(__original) function()
	{
		local result = __original();
		local i = ::TG.getFreeSlot(this);
		if (i != null)
		{
			local b = ::TG.getBuilding(this);
			result.Slots[i] = { Image = b.getUIImage(), Tooltip = b.getTooltip() };
		}
		return result;
	}

	q.onSlotClicked = @(__original) function( _i, _townScreen )
	{
		if (this.m.Buildings[_i] == null && ::TG.getFreeSlot(this) == _i)
		{
			local b = ::TG.getBuilding(this);
			this.m.CurrentBuilding = b;
			b.onClicked(_townScreen);
			return;
		}
		return __original(_i, _townScreen);
	}
});

// Tooltip text for the building (ids are plain strings the town screen passes to the backend).
::TG.HooksMod.hook("scripts/ui/screens/tooltip/tooltip_events", function( q ) {
	q.general_queryUIElementTooltipData = @(__original) function( _entityId, _elementId, _elementOwner )
	{
		if (_elementId == "world-town-screen.main-dialog-module.TrainingGrounds")
		{
			return [
				{ id = 1, type = "title", text = "Training Grounds" },
				{ id = 2, type = "description", text = "Drill one brother hard for a few days. He suffers a 25 per cent penalty to all attributes meanwhile, then three attributes of your choice are raised to the best a man of his background could have started with. Level-up gains stay." }
			];
		}
		return __original(_entityId, _elementId, _elementOwner);
	}
});

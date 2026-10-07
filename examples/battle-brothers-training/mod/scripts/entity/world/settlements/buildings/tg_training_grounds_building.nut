this.tg_training_grounds_building <- this.inherit("scripts/entity/world/settlements/buildings/building", {
	m = {},
	function create()
	{
		this.building.create();
		this.m.ID = "building.tg_training_grounds";
		this.m.Name = "Training Grounds";
		this.m.Description = "Drill a brother hard to push his raw talent to its limit";
		// Placeholder art: reuses the vanilla Training Hall picture.
		this.m.UIImage = "ui/settlements/building_07";
		this.m.UIImageNight = "ui/settlements/building_07_night";
		this.m.Tooltip = "world-town-screen.main-dialog-module.TrainingGrounds";
		this.m.TooltipIcon = "ui/icons/buildings/vet_hall.png";
		this.m.Sounds = [];
		this.m.SoundsAtNight = [];
	}

	function onClicked( _townScreen )
	{
		if (!this.World.getTime().IsDaytime)
			return;
		this.logInfo("Training Grounds: opened in " + this.getSettlement().getName());
		this.Tactical.EventLog.log("The training grounds of " + this.getSettlement().getName() + " are open to your men.");
		::TG.openWizard(this.getSettlement());
	}
});

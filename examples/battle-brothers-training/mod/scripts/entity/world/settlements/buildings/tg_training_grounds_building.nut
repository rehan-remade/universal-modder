this.tg_training_grounds_building <- this.inherit("scripts/entity/world/settlements/buildings/building", {
	m = {},
	function create()
	{
		this.building.create();
		this.m.ID = "building.tg_training_grounds";
		this.m.Name = "Training Grounds";
		this.m.Description = "Drill a brother hard to push his raw talent to its limit";
		// Own art (fal-generated, 410x275 like vanilla building pictures); shipped as gfx/ui/settlements/*.png in the zip.
		this.m.UIImage = "ui/settlements/tg_training_grounds";
		this.m.UIImageNight = "ui/settlements/tg_training_grounds_night";
		this.m.Tooltip = "world-town-screen.main-dialog-module.TrainingGrounds";
		this.m.TooltipIcon = "ui/icons/buildings/vet_hall.png";
		this.m.Sounds = [];
		this.m.SoundsAtNight = [];
	}

	function onClicked( _townScreen )
	{
		this.logInfo("Training Grounds: opened in " + this.getSettlement().getName());
		this.logInfo("The training grounds of " + this.getSettlement().getName() + " are open to your men.");
		::TG.openWizard(this.getSettlement());
	}
});

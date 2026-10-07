// Training Grounds: registers with Modern Hooks, builds MSU settings, installs the hooks.
::TG <- {
	ID = "mod_training_grounds",
	Name = "Training Grounds",
	Version = "1.0.0",
	Mod = null,
	HooksMod = null
};

::include("training_grounds/logic.nut");

::TG.HooksMod = ::Hooks.register(::TG.ID, ::TG.Version, ::TG.Name);
::TG.HooksMod.require("mod_msu >= 1.2.0");

::TG.HooksMod.queue(">mod_msu", function() {
	::TG.Mod = ::MSU.Class.Mod(::TG.ID, ::TG.Version, ::TG.Name);

	local page = ::TG.Mod.ModSettings.addPage("General");
	page.addRangeSetting("Days", 5, 1, 30, 1, "Training days", "Days the brother suffers the penalty before the training pays off.");
	page.addRangeSetting("CostBase", 500, 0, 5000, 50, "Base cost (gold)", "Fixed part of the price.");
	page.addRangeSetting("CostPerLevel", 150, 0, 1000, 10, "Cost per level (gold)", "Added for every level of the brother.");

	::include("training_grounds/game.nut");
	::include("training_grounds/hooks.nut");
});

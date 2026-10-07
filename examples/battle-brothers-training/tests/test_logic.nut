// Run with a plain Squirrel 3.x interpreter from the mod folder: sq tests/test_logic.nut
::TG <- {};
dofile("mod/training_grounds/logic.nut", true);
local L = ::TG.Logic;
local fails = 0;
function check( _name, _got, _want )
{
	if (_got != _want)
	{
		print("FAIL " + _name + ": got " + _got + ", want " + _want + "\n");
		fails++;
	}
}

// level 1 brother: no level-ups, start roll is the base value exactly
check("lvl1 start", L.estimateStart(50, 0, 0, 4, 47, 57, ::TG.LevelUp), 50);
check("lvl1 delta", L.delta(50, 0, 0, 4, 47, 57, ::TG.LevelUp), 7);
// already at the cap: nothing to gain
check("at max", L.delta(57, 0, 0, 4, 47, 57, ::TG.LevelUp), 0);
// never negative, even if base sits above the range for other reasons
check("above range", L.delta(80, 0, 0, 4, 47, 57, ::TG.LevelUp), 0);

// spec example shape: base 60 after 6 level-ups, bg range 47..56. Expected level gain is 12, so the
// start is estimated as 48 (the true start, 47, is not recorded by the game) and the result is 68.
check("spec delta", L.delta(60, 6, 0, 4, 47, 56, ::TG.LevelUp), 8);
check("spec result", 60 + L.delta(60, 6, 0, 4, 47, 56, ::TG.LevelUp), 68);

// gain bounds
local g = L.gainRange(0, 3, 0, ::TG.LevelUp);
check("gain min", g.min, 6);
check("gain max", g.max, 12);
local g3 = L.gainRange(0, 3, 3, ::TG.LevelUp);   // three stars: 4..5 per level
check("gain3 min", g3.min, 12);
check("gain3 max", g3.max, 15);
// beyond the 10 pre-rolled level-ups each level gives exactly 1
local gl = L.gainRange(0, 12, 0, ::TG.LevelUp);
check("late gain min", gl.min, 2 * 10 + 2);
check("late gain max", gl.max, 4 * 10 + 2);

// pending level-ups were not applied yet
check("applied", L.appliedLevelUps(5, 1), 3);
check("applied floor", L.appliedLevelUps(1, 0), 0);
check("applied neg", L.appliedLevelUps(2, 3), 0);

// estimate stays inside the possible window
local s = L.estimateStart(75, 8, 0, 0, 50, 60, ::TG.LevelUp);
check("window hi", s <= 60, true);
check("window lo", s >= 50, true);

// price
check("cost", L.cost(4, 500, 150), 1100);
check("cost floor", L.cost(0, 0, 0), 0);

if (fails == 0) print("OK\n"); else print("FAILED " + fails + "\n");

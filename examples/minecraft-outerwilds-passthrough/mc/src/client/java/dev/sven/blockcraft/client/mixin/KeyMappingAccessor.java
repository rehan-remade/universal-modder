package dev.sven.blockcraft.client.mixin;

import net.minecraft.client.KeyMapping;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/** The host cannot press Minecraft's keys itself (its window has the focus), so it sets them here. */
@Mixin(KeyMapping.class)
public interface KeyMappingAccessor {
	@Accessor("clickCount")
	int blockcraft$getClickCount();

	@Accessor("clickCount")
	void blockcraft$setClickCount(int clickCount);
}

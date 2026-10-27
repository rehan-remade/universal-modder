package dev.sven.blockcraft.client.mixin;

import com.mojang.blaze3d.pipeline.RenderTarget;
import dev.sven.blockcraft.client.FrameExporter;
import net.minecraft.client.renderer.GameRenderer;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Splits the frame into the world layer and the overlay (hand, effects, GUI).
 *
 * <p>The world is copied just before the 3D HUD is drawn; what is drawn after that is the overlay.
 *
 * <p>{@code required} means a failed injection is a hard error, so if Minecraft's method names drift the
 * mod reports it instead of silently compositing nothing.
 */
@Mixin(GameRenderer.class)
abstract class GameRendererMixin {
	@Shadow @Final private RenderTarget mainRenderTarget;

	// DISABLED: this targets the wrong argument. `@At` on LevelRenderer.render(...ZZ)V with index = 5
	// was written believing index 5 is "should render sky". Disassembling GameRenderer.renderLevel shows
	// the two trailing booleans are actually:
	//   index 5 = !bossOverlay.shouldCreateWorldFog()   -> fog
	//   index 6 = !appliedPostEffects.isEmpty()         -> post-processing present
	// So with a host attached the mod was turning world fog off, not the sky. Left here, disabled, until
	// the real cause of the flat colour layer is settled.
	//
	// @ModifyArg(
	// 	method = "renderLevel",
	// 	at = @At(value = "INVOKE", target = "Lnet/minecraft/client/renderer/LevelRenderer;render(Lcom/mojang/blaze3d/resource/GraphicsResourceAllocator;ZLnet/minecraft/client/renderer/state/level/CameraRenderState;Lcom/mojang/renderpearl/api/buffers/GpuBufferSlice;Lorg/joml/Vector4f;ZZ)V"),
	// 	index = 5
	// )
	// private boolean blockcraft$noSky(final boolean shouldRenderSky) {
	// 	return shouldRenderSky && !BlockCraft.active;
	// }

	@Inject(
		method = "renderLevel",
		at = @At(value = "INVOKE", target = "Lnet/minecraft/client/renderer/GameRenderer;render3dHud(Lnet/minecraft/client/renderer/state/level/CameraRenderState;Lnet/minecraft/client/renderer/state/level/PlayerRenderState;Lnet/minecraft/client/renderer/state/OptionsRenderState;Z)V")
	)
	private void blockcraft$captureWorld(final CallbackInfo ci) {
		FrameExporter.captureWorld(this.mainRenderTarget);
	}

	@Inject(method = "render", at = @At("TAIL"))
	private void blockcraft$captureOverlay(final CallbackInfo ci) {
		FrameExporter.captureOverlay(this.mainRenderTarget);
	}
}

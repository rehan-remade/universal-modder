# Minecraft: Forge 1.7.10 concepts on Fabric 1.20.1

Every row was reproduced in a real port: Thaumcraft 4.2.3.5 → 1.20.1 Fabric (Fabric API 0.92.12, Yarn
1.20.1+build.10, Loom 1.7.4). Rows are checked by a GameTest or a client screenshot unless they say otherwise.
Field note: `knowledge/games/minecraft/porting-thaumcraft-4-1-7-10-forge-to-minecraft-1-20-1-fabric.md`.

Look names up on the mapped jar in the Loom cache (`javap -cp <minecraft-merged ...yarn...jar> <class>`).
`javap -c -p` shows lambda names and local-variable slots for mixins. Names below are Yarn names.

## Interaction and item hooks
| 1.7.10 Forge | 1.20.1 Fabric | Notes |
|---|---|---|
| `Item.onItemUseFirst` (ran **before** the block's `onBlockActivated`) | `UseBlockCallback` (fires before the block, both sides); return non-PASS to stop the block | In 1.20 `Block.onUse` runs first and `Item.useOnBlock` only if the block passes. Find every `onItemUseFirst`: keys and wands depend on the old order |
| `Item.onEntitySwing` (every swing packet) | mixin on `ServerPlayNetworkHandler` hand-swing handling, forwarding to the item | Hooking only block-break start misses swings at air |
| `Item.onBlockStartBreak` | `PlayerBlockBreakEvents.BEFORE` | Can cancel the vanilla break and do its own |
| `Item.onLeftClickEntity` | `AttackEntityCallback` | |
| `Item.getEntityLifespan` / `ItemExpireEvent` | mixin on `ItemEntity` | |
| Forge bow nock / loose events | mixin on `BowItem` | The mod's own bow handles it in its class |
| `Item.addInformation(stack, player, list, adv)` | `appendTooltip` has no player: fetch the client player | Tooltips that showed per-player numbers (discounts) lose them silently otherwise |
| `ItemCraftedEvent` | mixin on `CraftingResultSlot.onTakeItem` **plus** explicit calls from each of the mod's own result paths | The original fired it from its own machines too |
| `HarvestDropsEvent` | mixin on `Block.getDroppedStacks` (variant with the breaking entity) | |
| `EntityJoinWorldEvent` cancel | `ServerEntityEvents.ENTITY_LOAD`; check `age == 0`; queue `discard` with `server.send(new ServerTask(...))` | `server.execute` runs at once on the server thread |
| `NoteBlockEvent.Play` | mixin at the `World.addSyncedBlockEvent` call in `NoteBlock.playNote` | Setting the state directly does not recompute `instrument` |
| player jump event | mixin on the player's jump | |
| IMC messages from addons | a public static API keyed by registry keys | No IMC in Fabric |
| key bindings | `KeyBinding.wasPressed()` counts OS key repeats; drive toggles from press edges | Vanilla 1.20 owns F (swap hands): swallow it while the mod's item is held |

## Blocks, items and data
| 1.7.10 Forge | 1.20.1 Fabric | Notes |
|---|---|---|
| block / item + metadata | one flattened id per (id, meta); each port item registers the legacy reference it replaces; a resolver for data files | Fail at startup on an unregistered catalogue entry. Metadata-agnostic checks (`Blocks.sand`, any meta) cover several 1.20 blocks (sand and red sand) |
| separate "lit" blocks (`lit_redstone_ore`, `lit_furnace`) | block states | Data aimed at them has no block to attach to |
| `hasTileEntity(meta)` true only for some metas | only those blocks implement `BlockEntityProvider` | Otherwise world generation queues dummy block entities and logs "Tried to load a block entity" |
| `getBlockHardness` reading config | hardness is baked into `AbstractBlock.Settings`; a mixin on the state's hardness returns the live value | Client and server must agree, or mining prediction breaks on servers with another config |
| `setResistance(r)` | `strength(hardness, r * 3 / 5)` (project convention; the 1.7.10 source of the factor was not re-checked) | Raw `getExplosionResistance` overrides keep their value |
| `getLightOpacity`, `isOpaqueCube` false, render pass 1 | `nonOpaque()`, a `getOpacity` override, translucent layer | Per-instance opacity from a block entity fails: the light engine runs off-thread; carry it in an `IntProperty` |
| `isLadder` | climbing is the `#minecraft:climbable` tag on the state; data-dependent climbing needs a `LivingEntity` mixin | Camouflage blocks must also forward collision, landing, display ticks and clicks |
| dragon / wither immunity | `#minecraft:dragon_immune`, `#minecraft:wither_immune` | |
| leaf "decaying" flag | `PERSISTENT == false` and `DISTANCE == 7` | |
| crop `updateTick` growth | `randomTick` | Growth accelerators must call `randomTick` |
| `getDrops(world, x, y, z, meta, fortune)` | loot tables evaluated with a tool stack: give machines a synthetic pickaxe carrying the fortune / silk level | |
| ores → smelted ingots | 1.20 ores drop raw metal and have deepslate variants | Extend ore-processing tables to raw metal and deepslate ores |
| ore dictionary names | `c:` convention tags (`c:ores`, `c:iron_ingots`, `c:raw_iron_ores`...) | Not the same set as a name match; rebuild tag-derived lookups on `TAGS_LOADED`; gate recipes with the `fabric:item_tags_populated` condition |
| `DoorBlock` subclass | 1.20 `DoorBlock.setOpen` plays the block-set-type sound | Make sure only the original sound plays |
| integer dimension ids in saved links | dimension identifiers | Tooltips that showed the provider name now show the id |
| enchantment weight (any int) | `Enchantment.Rarity` (10 / 5 / 2 / 1 only) | Keep the enchantability formulas |
| enchanting power `getEnchantPowerBonus` | `#minecraft:enchantment_power_provider` (1 each) plus a `@ModifyVariable` before `Random.setSeed` in `EnchantmentScreenHandler.method_17411` | |
| `DamageSource` flags (`isUnblockable`, magic, fire, explosion) | damage-type tags (`#bypasses_armor`, `#witch_resistant_to`, `#is_fire`, `#is_explosion`, `#is_fall`) and new damage types | `generic` is in `#bypasses_armor` |
| `ISpecialArmor` | port `ApplyArmor` as is and run it from a mixin on `applyArmorToDamage` only for wearers of a special piece | Everyone else keeps 1.20 numbers |
| Baubles (AMULET, RING, RING, BELT) | Accessories' default `necklace` x1, `ring` x2, `belt` x1 | Keep a thin `BaublesApi` facade; Accessories as a compile-only, `suggests` compat module |
| Forge `Configuration` `.cfg` | a small reader / writer for the Forge syntax, loaded first in `onInitialize`; a server-to-client config packet sent last on join | Keeps users' config files and docs valid |
| `BlockFluidClassic` | vanilla `FlowableFluid` with the same reach; tick rate = viscosity / 200; `Material.water` → `#minecraft:water` | `#minecraft:water` also means swimming, drowning, sponges, lava → obsidian |
| `BlockFluidFinite` | a custom block with quanta per block | Vanilla buckets only pick up `FlowableFluid` sources |
| `setBlockToAir` on a fluid | `setBlockState(pos, AIR, 3)` | `removeBlock` on a fluid writes the fluid state's block: the fluid itself |
| potion icons from a sheet (`setIconIndex`) | one 18 x 18 texture per `mob_effect` | |
| effects with an empty curative-item list (milk can't cure) | mark the effect; mixins on the milk bucket and `LivingEntity` skip it | Save the mark with the entity |
| potion damage values in loot and trades | map each drinkable / splash value with an effect to its 1.20 potion | |
| icons switched in code (`getIcon(stack, pass)`) | item model overrides on registered predicates | If the original stored the icon on the `Item` singleton, every stack changes at once |
| `MaterialAiry` / mobility flag 1 | `pistonBehavior(PistonBehavior.DESTROY)` in the block settings | Material no longer carries behaviour |
| a block drawn only by its block-entity renderer | still needs a blockstate JSON | Otherwise a missing-blockstate warning |
| `GameRegistry.registerFuelHandler` | `FuelRegistry.INSTANCE.add` | Speeding up vanilla furnaces needs an accessor mixin on their progress |
| fixed world height 0..256 | read the world's bottom and top | Tree generators and vertical scans hard-code it |
| tool damage (constant per tool type, no cooldown) | keep the 1.7.10 constants (sword 4, shovel 1, pickaxe 2, axe 3, plus material) with 1.20 attack speeds | |
| 1.7.10 recipe registration | a bare Block ingredient is every variant; a bare Item is meta 0 | Put the rule into the extractor |
| shaped recipe with blank rows / columns | 1.20 trims them | A recorded deviation |
| NBT outputs, strict NBT inputs, smelting into several items | custom recipe serializers; Fabric's `fabric:nbt` ingredient | Vanilla 1.20.1 JSON cannot express them |
| mixed-case asset paths, junk files in the jar | lower-case every path and its references; skip non-identifier names | Convert `.lang` to JSON, keeping old keys and adding `item.<ns>.<id>` |
| own save files (`.thaum`, `labyrinth.dat`) | an overworld `PersistentState`, per player UUID | Keep the original NBT tag names |
| `LivingHurtEvent` (before armour) | mixins on `LivingEntity` and on `PlayerEntity` changing the amount before armour | |
| attribute added to every `EntityMob` at construction | mixin on `HostileEntity`'s attribute container | |

## Entities and AI
| 1.7.10 | 1.20.1 | Notes |
|---|---|---|
| `EntityAITasks` (polled every 3rd tick) | `GoalSelector` (every 2nd tick) | Delay counters inside start conditions fire at a different interval |
| `updateEntityActionState` steering | the routine in `mobTick` with the move / jump controls disabled | |
| pathfinding onto a block | `startMovingTo` stops within about a block | Path to the exact point, or the air above a solid target |
| entity `yOffset` (centred box) | positions are the bottom of the box | Convert spawn positions |
| int `x, y, z` passed as entity coordinates | spawns on the block corner | A quirk to keep or fix deliberately |
| `jumpMovementFactor` | mixin on `getOffGroundSpeed`; per-tick pushes from a mixin at `travel` | |
| zombie subclass with the villager variant | zombie villagers are a separate type | Reimplement the variant in the subclass |
| subclass of a vanilla mob | the 1.20 superclass adds behaviour 1.7.10 lacked (drowned conversion, reinforcements, baby / villager variants, random gear) | List what the 1.20 parent does and switch off what the original did not have |
| behaviour inherited from 1.7.10 vanilla (big-oak generator, slime hops, old flight, villager model, zombie box 0.6 x 1.8) | 1.20 vanilla differs | Port the 1.7.10 vanilla parts too |
| a 1.7.10 AI task (`AIAttackOnCollide` with a class filter) | port it as its own goal, line by line | The nearest 1.20 goal changes reach and memory |
| sneak-click with an item in hand reaching the block | a sneaking player holding an item never reaches `Block.onUse` | The port documented it as a deviation; `UseBlockCallback` (fires before that check) was not tried |
| one click: item hook, then the replaced block's activation | open the new block's screen explicitly after converting | 1.7.10 activated the block just placed by the hook |
| `Village` (centre, radius) | the nearest meeting-point POI (bell); radius ~19 | Profession villagers need 1 experience or `LoseJobOnSiteLossTask` removes the profession |
| `EntityList` names in hashes / research triggers | ship a 1.20 id → 1.7.10 name map | |
| cross-dimension follow | `FabricDimensions.teleport` | |
| `EntityFX` classes | particles; but first check the original ever calls them | 7 of TC4's FX classes and 3 of its packets were dead code |
| item entity counter-gravity lift | 1.20 applies buoyancy instead of gravity in liquids | Add the lift only on ticks that apply gravity |
| flight granted by gear | reset `ServerPlayNetworkHandler.floatingTicks` each tick | Otherwise the server's flying kick applies |
| `ServerPlayerEntity` step height | 1.0 already on the server | Raise step height on the client only, as 1.7.10 mods did |

## World generation
| 1.7.10 | 1.20.1 | Notes |
|---|---|---|
| `IWorldGenerator.generate` (after vanilla populate) | features in `TOP_LAYER_MODIFICATION`, keeping the generator's internal order | Keep its world-type checks; cap Nether heights at 128 |
| writes into neighbouring chunks | a feature may write only its chunk plus a small margin | Split the generator; shift `decorate(x, z)` frames by -8 |
| `BiomeManager.addBiome` (overworld) | Fabric API 0.92 has no overworld biome injection | The port wrapped `MultiNoiseBiomeSource` with a mixin, about 256-block regions rolled at the original odds. The biome must also join the source's biome list, or `BiomeModifications` gives it no features. TerraBlender is the usual library route |
| `BiomeDecorator` defaults (lakes, dungeons, ores, carvers) | a biome JSON has only what it lists | Copy the vanilla carvers and non-vegetation features into each ported biome |
| `BiomeGenBase` defaults: spawn lists, `topBlock`, computed sky colour | datapack biomes have none of them | Write the 1.7.10 default spawns into each biome (unless the original cleared them); store the sky colour from the 1.7.10 formula; sample the real surface where code used `topBlock` |
| Forge `BiomeDictionary` types, "hills" variants | biome tags (`c:forest`, `c:wasteland`, or the mod's own); 1.18 merged hills into their parents | |
| tree generators placing leaves | schedule a block tick per leaf so 1.20 computes `DISTANCE` | |
| static scratch lists in generator helpers | per-thread lists when generation runs off-thread | |
| neighbour updates during populate | compute neighbour-dependent states yourself after generating | |
| long runs of `setBlock` (hand-written structures) | extract the placements by script into a data file; keep only the random choices in code | |
| `MapGenScatteredFeature` hooks (pyramids, temples, huts) | let the chunk holding the structure start place the addition once | |
| 2D biomes per column | 3D biome cells (cave biomes underground) | Ported logic should read the surface biome; `getBiome` is blended, `getBiomeForNoiseGen` reads the stored cell |
| `StructureVillagePieces` components | jigsaw templates, generated by replaying the build code; injected into vanilla house pools at `SERVER_STARTING` with scaled weights | Enforce per-village limits with a mixin on `StructurePoolGenerator` |
| `ChestGenHooks` categories | 1.20 chest loot tables (the 1.7.10 "blacksmith" is the weaponsmith) | |
| custom dimension (`WorldProvider`) | datapack dimension + dimension type + a biome whose feature builds the content | The GameTest server has no datapack dimensions. A void flat world needs one `structure_void` layer. Patch the "experimental" check |
| site checks tuned for 1.7.10 terrain | rarely pass on 1.20 terrain | Count rolls against placements before concluding generation works |

## Rendering (details in `knowledge/techniques/porting-1-7-10-gl11-render-states-and-iitemrenderer-frames-t.md`)
| 1.7.10 | 1.20.1 | Notes |
|---|---|---|
| `ISimpleBlockRenderingHandler` | baked / FRAPI models; static neighbour-dependent faces become block-state properties plus generated models | Sodium needs Indium for FRAPI models |
| `IItemRenderer` | `BuiltinItemRendererRegistry`, replaying the 1.7.10 frame per `ModelTransformationMode` | The INVENTORY_BLOCK frame is (30, -45, 0), not vanilla 1.20's (30, 225, 0) |
| `glAlphaFunc`, `GL_ADD`, `GL_LIGHTING` off | custom core shaders registered through `CoreShaderRegistrationCallback` | |
| texgen / texture-matrix starfields | one core shader, checked against a numeric emulation of the old pipeline | |
| `ShaderGroup` post effects | `PostEffectProcessor` at HUD time | GLSL 120 → 150; move global-initialiser work into `main()` |
| `Block.addHitEffects` | mixin on `ParticleManager.addBlockBreakingParticles` | |
| custom crack progress | `WorldRenderer.setBlockBreakingInfo` | |
| Forge block-highlight event | `WorldRenderEvents.BEFORE_BLOCK_OUTLINE` (can cancel vanilla's) | World overlays drawn at `LAST` with `ctx.consumers()` never appear; use `AFTER_ENTITIES` |
| additive item draw (`glBlendFunc(SRC_ALPHA, ONE)`) | a wrapped `VertexConsumerProvider` mapping every layer to an additive one | |
| Forge `WavefrontObject` OBJ | flip V and inset UVs by 0.0005 towards the face's average | |
| 6 or 8 px textures | upscale by whole factors (nearest neighbour) | One small texture caps the whole atlas's mip levels ("limits mip level from 4 to 1") |
| blue water sprite | 1.20's is grey: tint with the biome water colour | Also in GUIs |
| armour textures and `ModelBiped` | material layer textures; Fabric `ArmorRenderer` for custom shapes | Copy the original's pass order for dyed pieces |
| client keyboard read in common code | worked only in single player | Flag it; send a packet instead |
| `ModelBase` models, `.obj` meshes | `ModelPart`s (same box UV unwrap, original textures fit), converted by a script; a small OBJ loader with named parts | |
| particle layers on custom sheets | a 1.20 `ParticleTextureSheet` per layer; turn the lightmap on in its `begin()` | A CUSTOM particle flushed earlier turns it off: every additive particle went black |
| random per-face textures by position hash | weighted blockstate variants (a stand-in, not face-identical) | |
| `GL_EXP` fog with a density | linear fog ending at 3 / density (`BackgroundRenderer` mixin) | |
| `Mouse.isButtonDown` (LWJGL2), depth-trick clipping | GLFW polling; a scissor | |
| standard galactic font, forced unicode | `minecraft:alt`, `minecraft:uniform` | `achievement_background.png` is gone |
| faces lit by the block's own brightness (`renderFace*`) | 1.20 chunk mesh faces take light from the neighbour | An emitter at 12 shows 11 on unshaded faces |

## Build and test
- Check every Loom version gate: a mod jar whose manifest says a newer `Fabric-Loom-Version` refuses to remap.
- Declare mod dependencies `transitive = false`.
- Jar-in-jar libraries of test-only mods are not loaded in dev runs: add them to the classpath yourself.
- Stub what a sandbox cannot download in a test-only source set (never shipped).
- Run the release jar on a real server and a production-style client, not just the dev runtime.
- Never trust "passes" without the JUnit file: `knowledge/techniques/fabric-1-20-1-gametests-as-the-oracle-of-a-large-mod-port.md`.

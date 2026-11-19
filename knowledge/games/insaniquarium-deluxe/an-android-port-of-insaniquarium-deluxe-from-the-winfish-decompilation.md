---
kind: game
title: An Android port of Insaniquarium Deluxe from the WinFish decompilation on PopLib (SDL3), widescreen for a foldable and a tablet
game: Insaniquarium Deluxe
games_also: []
game_version: "Steam app 3320, Insaniquarium.exe md5 1314be36cbd1d79a6816c48b273a5b22 (decomp targets 1.1); assets from the user's own copy"
platform: other
engine: native
route: decomp-recomp
tools: ["Vindirect/WinFish decompilation (61ddba1)", "SaMeiers/insaniquarium-port (AGPL-3.0, 95d4aaf)", "SaMeiers/PopLib fork (SDL3 rewrite of SexyAppFramework, 45776ce)", "libopenmpt 0.8.9", "Android NDK r27d (27.3.13750724)", "Android SDK cmdline-tools 23.0 / android CLI", "CMake 4.1.2", "Gradle 8.12 + AGP 8.7.3", "JDK 22", "Visual Studio 2022 (desktop test build)", "Qwen-Image-Edit 2509 fp8 + Lightning 8-step LoRA in ComfyUI 0.24 (wide art)"]
anti_cheat: "none (offline single-player game)"
status: in-progress
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-16'
links:
- "https://github.com/vindirect/winfish"
- "https://github.com/SaMeiers/insaniquarium-port"
- "https://github.com/SaMeiers/PopLib"
- "https://github.com/teampopwork/poplib"
- "https://lib.openmpt.org/libopenmpt/"
tags: [android, apk, popcap, sexyapp, sexyappframework, poplib, sdl3, decompilation, native-port, touch, lifecycle, ndk, headless-testing, widescreen, aspect-ratio, foldable, galaxy-z-fold7, tablet, galaxy-tab-s11-ultra, outpainting, qwen-image-edit]
---
# An Android port of Insaniquarium Deluxe from the WinFish decompilation on PopLib (SDL3), widescreen for a foldable and a tablet

> Insaniquarium Deluxe (PopCap, 2004) as a native arm64/armv7 Android APK, built from the community WinFish
> decompilation on PopLib, an SDL3 rewrite of PopCap's SexyAppFramework, with the player's own Steam files packed
> into a local-only APK. The existing community port had an Android target that did not build from git. This
> work completed it and added what a phone needs: fullscreen, the back button, saving when Android backgrounds the
> app, no keyboard popping up at launch, two-finger "collect all coins", and a launcher icon. It also fills any
> screen shape instead of letterboxing. On the Fold7 cover (21:9) and the Tab S11 Ultra (16:10) the tank gets
> wider and the fish use all of it; on the Fold7 inner screen (~10:9) it shows more floor. The game refits live
> when the Fold changes screens, and the sides are AI-extended art made from the player's own pictures.
>
> The APK passes static checks, and the same code was played headless on a desktop build through a scripted
> test driver. It has **not** run on a phone or emulator yet: this PC has no hypervisor, and the user sideloads it.

## Setup
- Game: Steam app 3320. Assets are loose files with no `main.pak`: `data/` (bitmap fonts), `images/` (gif/jpg
  with alpha masks), `sounds/` (ogg, au), `music/` (three `.mo3` modules), `properties/resources.xml`,
  `fishsongs/`. About 9.4 MB of what the game reads.
- `SaMeiers/insaniquarium-port` with submodules `external/winfish` (the decomp, unmodified) and `poplib`
  (SaMeiers' PopLib fork). `port/port.sh` re-derives `port/winfish/` from the decomp every run: it rewrites
  includes and renames framework types, then applies Python fixup scripts. Game changes live in those scripts,
  never in the decomp.
- Android SDK in a user folder. In cmdline-tools 23.0 `sdkmanager` is a deprecated shim; packages install
  with `android --no-metrics --sdk=<dir> sdk install "ndk;27.3.13750724" "cmake;4.1.2" "platforms;android-35"
  "build-tools;35.0.0" platform-tools`, and the CLI says `--licenses` "is no longer needed". The user approved
  accepting the SDK licence.
- JDK 22 runs Gradle 8.12 / AGP 8.7.3 fine.

## Route and why
`decomp-recomp`, reusing everything that exists. WinFish is "fully playable" C++ decompiled from the 1.1 exe.
PopLib replaces DirectDraw/Win32 with SDL3, and the SaMeiers port already runs it on Windows and Linux
handhelds (PortMaster), with framework bugs fixed (see its `PORT-CHANGES.md`). Writing a fresh port or a
reimplementation would have repeated all of that. Running the Windows exe under Winlator/Box64 is not a port.

## How the game works (what we had to learn)
- **Two framework layers.** Game code is `WinFishApp : SexyApp : PopLib::AppBase`. `AppBase` owns the SDL
  event loop (`ProcessDeferredMessages`), the widget manager and the sound manager, so the phone hooks
  belong there as virtuals that the game overrides.
- **Updates run at 100 a second** (`AppBase::UpdateFrames`, which WinFishApp overrides and chains down to).
  Music (`OpenMptMusicInterface`) is refilled from that update on the main thread. Sound effects play on
  OpenAL Soft's own mixer thread.
- **Saves.**
  - Everything goes to `GetAppDataFolder()/userdata/`: `users.dat`, `user<N>.dat`, and the in-progress tank
    as `<mode><N>.dat` (e.g. `adv1.dat`).
  - Settings go to a JSON "registry" at `GetAppDataFolder()/PopCap/Insaniquarium/registry.json`.
  - On Android `GetAppDataFolder()` is `SDL_GetPrefPath("", "PopLib")`, which is internal storage.
- **Saving.** `Board::SaveCurrentGame()` saves the tank when you leave it, or erases the save when the board
  says it shouldn't be kept. `WinFishApp::SaveCurrentUserData()` saves the profile. Shutdown and leaving a tank
  call both. A later Start Adventure offers "Continue game?".
- **The in-game menu** is the Options dialog. The Board's top-right Menu button is a ButtonWidget with id
  123, and pressing it calls `DoOptionsDialog(false)`. The dialog's own OK calls
  `WinFishApp::ApplyOptionsSettings()`, which applies the settings and kills the dialog. Killing it
  unpauses the board.
- **The game never handles Escape.** No `KEYCODE_ESCAPE` anywhere in the decomp, so a phone's back button
  needs a meaning given to it.
- **Assets.**
  - PopCap's alpha masks are grey images named `_name.gif` or `name_.gif` beside the colour image.
  - `smallswim.gif` is 10 frames × 5 rows of 80×80: small, medium and large guppy, king guppy, carnivore.
  - `resources.xml` has unquoted attribute values; the PopLib fork's parser quotes them.
- **Second-launch prompt.** The second launch asks "check for updates?" through `SexyApp::ShouldCheckForUpdate`
  unless `mDontUpdate` is set. The registry or `partner.xml` can set it.

## Build steps
1. `git clone --recurse-submodules https://github.com/SaMeiers/insaniquarium-port`. It aborts on a dead
   submodule (gotcha 1); finish with
   `git -c submodule.external/discordrpc.update=none submodule update --init --recursive --force` inside
   `poplib`.
2. `bash port/port.sh`, then `bash port/copy-assets.sh "<game dir>"`. That copies to `port/bin` and runs
   `verify-assets.py`. Add `python port/verify-assets.py --fix-case` for the Steam copy's case mismatches:
   65 files plus 21 alpha companions.
3. Things the Android target was missing:
   - **An activity class.** The manifest names `org.winfish.insaniquarium.InsaniquariumActivity`; add it as an
     `SDLActivity` subclass whose `getLibraries()` returns only `"main"`. SDL3 is linked statically into
     `libmain.so`, and `libc++_shared.so` is found by the system linker as a DT_NEEDED.
   - **Asset packaging.** Copy the six game folders into a gitignored dir and point
     `sourceSets.main.assets.srcDirs` at it. PopLib reads them straight from the APK through
     `SDL_IOFromFile`. The APK then holds PopCap's files, so it stays on your own devices (see Assets).
   - **BASS off** (`-DPOPLIB_WITH_BASS=OFF`), and the `libbass.so` jniLibs dir removed. PopLib prefers
     libopenmpt for the `.mo3` music anyway.
4. `local.properties`: `sdk.dir=D:/path/to/android-sdk` (forward slashes; gotcha 4).
5. `gradlew assembleDebug` with `JAVA_HOME` and `ANDROID_HOME` set. The output has `arm64-v8a` and
   `armeabi-v7a`, minSdk 24, targetSdk 35. A clean build takes about 5 minutes; incremental, under a minute.
6. Phone changes, as PopLib virtuals (all `#ifdef __ANDROID__`) plus a game fixup script:
   - `AppBase::EnteredBackground()` / `EnteringForeground()`, called from an `SDL_AddEventWatch` callback on
     `SDL_EVENT_DID_ENTER_BACKGROUND` / `SDL_EVENT_WILL_ENTER_FOREGROUND` (gotcha 7).
     - The base writes the registry and pauses OpenAL with `ALC_SOFT_pause_device` (through
       `alcGetProcAddress`); foreground resumes it.
     - The game override saves the profile and the current tank, the same calls quitting makes.
   - Back button:
     - Set `SDL_HINT_ANDROID_TRAP_BACK_BUTTON` before `SDL_Init`.
     - In the key handler, `SDLK_AC_BACK` goes to a virtual `BackButtonPressed()` first and to the widgets as
       Escape otherwise. The key-up of a handled press is dropped.
     - What the game does with it:
       - With the Options dialog open, back closes it through `ApplyOptionsSettings()`.
       - In a tank, back taps the Menu button (`ButtonPress(123)` then `ButtonDepress(123)`), but only if it
         is visible and enabled.
       - On the main menu, back calls `SDL_SendAndroidBackButton()`, which sends the app to the background.
   - Always fullscreen: `mIsWindowed = false; mForceFullscreen = true` before `MakeWindow` (gotcha 9).
   - No `SDL_StartTextInput` at window creation (gotcha 6).
   - Two-finger tap:
     - Count `SDL_EVENT_FINGER_DOWN` and `SDL_EVENT_FINGER_UP`/`CANCELED` yourself. When a second finger
       lands, call `TwoFingerTap()`.
     - The game runs the port's existing Auto Collect (`Board::CollectAllCoins()`) if that option is on.
       Android's prompt for that option mentions the gesture.
   - `mDontUpdate = true` after `partner.xml` is read (gotcha 10).
7. Optional launcher icon: draw the large guppy from the player's own `smallswim.gif` over `aquarium1.jpg`
   water into a gitignored res dir. Choose it with a gradle `manifestPlaceholders` entry, so the tree still
   builds with the stock icon when it hasn't been generated.
8. Add `android:appCategory="game"` so Samsung's Game Launcher lists the app.

## Widescreen for a foldable and a tablet
The user plays on a Galaxy Z Fold7 and a Galaxy Tab S11 Ultra, so a 4:3 picture between black bars was not
good enough. Their screens in landscape, and the screen size the game gets:

| Screen | Pixels | Aspect | Game screen |
|---|---|---|---|
| Fold7 cover | 2520×1080 | 21:9 | 1120×480 |
| Tab S11 Ultra | 2960×1848 | 16:10 | 768×480 |
| Fold7 inner | 2184×1968 | ~10:9 | 640×576 |

- **PopLib side.** SexyAppFramework already supports a display larger than the game: `mScreenBounds` and
  `WidgetManager::Resize(mouseDestRect, mouseSourceRect)` translate all widget drawing and remap the mouse. So
  the game keeps its 640×480 coordinates everywhere, and the margins are simply at negative x, past x 640 and
  past y 480.
  - The fork had an unused `mWidescreenAware` flag; it now sizes the screen to the display's aspect up to a
    maximum (1200×640). Extra width is split left/right; extra height goes below, so the HUD bar stays at the
    top.
  - The screen is refitted on every `SDL_EVENT_WINDOW_(PIXEL_SIZE_CHANGED|RESIZED)`, because the Fold moves a
    running app between its two screens. `SDLInterface::SetScreenSize` recreates the screen texture.
  - The game draws the margins through a hook. If it doesn't, the interface fills them at present time with a
    dimmed mirror image of the screen's edges, faded to black outward. It can't be done inside the frame:
    a texture can't be both the source and the target of a copy.
- **Game side, as one fixup script with exact match counts.** About 60 x bounds become `WIDE_L(n)` / `WIDE_R(n)`
  (n minus the left margin, or plus the right one). That covers fish and breeders 10–540, large fish 0–480,
  aliens, missiles, pets, food and larvae, the `rand % 520 + 20` spawns (15 places), and tap-to-feed 31–586.
  - **Not edges, so left alone:** 550 in Coin, Larva and part of Food (where collected things fly, i.e. the
    money counter); Fish's 250/175 swim pattern around the middle; the bubble machine's and alien attractor's
    fixed spots, which sit on scenery.
  - **Drawing the tank.** The background is drawn wide; its glass panes (x 0–32 and 610–639 in all six
    pictures) are redrawn at the screen's edges. The water-surface wave pieces stay at the edges with the
    middle cel tiled between, cut rather than overlapped because the waves are additive. The floor light is
    tiled and the shadow mask mirrored.
  - **HUD and taps.** The HUD bar is extended with a 5-px slice of plain brass and capped with its frame edges.
    The bottom text moves to the screen's bottom. The board widget gets negative `mMouseInsets`, so taps in the
    margins feed.
  - Fish and aliens are top-level widgets, so they draw and take taps in the margins with no further changes.
    The board and its overlay widget set a clip rect larger than themselves (`Graphics::SetClipRect` only
    intersects with the screen).
  - **Folding mid-game.** `Fish`/`Breeder` store their limits when created, so those are shifted by the change,
    and anything left off screen is moved back.
  - **Menus** stay 4:3 in the middle. The title, main menu and store draw wide art in their margins (margins
    only: a menu isn't redrawn every frame). Everything else gets the faded reflection, and so does the bottom
    of a tall screen.
- **Wide art from the player's own copy.** Qwen-Image-Edit 2509 fp8 with the 8-step Lightning LoRA, in ComfyUI:
  - Each picture loses its glass panes and goes on a 1200×480 canvas at x 280.
  - Masked inpainting (`SetLatentNoiseMask`) paints the sides over a colour guide: the picture mirrored outward
    and blurred.
  - The model may repaint 44 px into the original. The original is pasted back with a 48 px fade.
  - Each picture takes about 50–100 s on a 4090 that was also busy with another job.
  - The pictures are drawn at runtime when present, with the mirrored scene as the fallback.

## Verification
- **Static APK checks** (a script):
  - `aapt2 dump badging` shows the launcher activity, and the activity class is in the dex.
  - For both ABIs, `llvm-readelf -d libmain.so` NEEDED lists only system libs plus the bundled
    `libc++_shared.so`.
  - `llvm-nm -D` shows `SDL_main`, `JNI_OnLoad` and the `Java_org_libsdl_app_SDLActivity_*` natives exported.
  - LOAD segments are aligned to 0x4000, and `zipalign -c -P 16` passes (16 KB pages on Android 15+).
  - All 602 staged asset files are in the APK.
  - The APK is 48 MB. Each `libmain.so` (14.4 MB arm64, 10.8 MB v7a) is stored uncompressed.
- **A scripted test driver in PopLib** (`misc/testscript.cpp`):
  - It is off unless `POPLIB_TEST_SCRIPT` names a file. Each line is `<update> <command> [args]`; commands
    are move, click, key, type, back, background, foreground, twofinger, shot, log, quit and kill.
  - `kill` is `std::_Exit`, i.e. Android killing a background app.
  - It calls the Android hooks directly. A desktop MSVC build of the same tree therefore exercises the
    phone-only game logic headless, with `SDL_VIDEO_DRIVER=offscreen`, `SDL_RENDER_DRIVER=software`,
    `ALSOFT_DRIVERS=null` (silent) and `LOCALAPPDATA` pointed at a scratch dir.
  - Screenshots are read back from PopLib's `mScreenTexture`.
- **What the screenshots showed:**
  - Title, then the New User dialog, then the main menu.
  - Adventure goes to the instructions screen, where back correctly does nothing, and then to tank 1-1, where
    feeding costs $5.
  - Back opens the Options menu, and back again closes it.
  - `background` then `kill` (no shutdown) leaves `adv1.dat`, `user1.dat` and `registry.json` written. The next
    launch says "Welcome back" and offers "Continue game?" with the same $190 tank.
  - With Auto Collect on, each two-finger tap sent the coins on screen flying to the counter: $55 → 90 → 125
    → 160.
- **Widescreen**, with `POPLIB_DISPLAY_SIZE` set to each device's pixels, plus the driver's `display WxH`
  (fold or unfold) and `winshot` (the window as presented, reflections included):
  - All three shapes reach the right screen size and play.
  - Food dropped only in the far-left margin is found by the fish, which swim out, eat, grow ("Your fish has
    grown!") and drop coins.
  - Unfolding mid-tank (1120×480 → 640×576) and folding again works.
  - The menus show their wide art on wide screens and the faded reflection below on the 10:9 screen.
- **Not verified:** anything on a real Android device or emulator.
  - Not run there: GLES rendering, OpenSL audio and the real pause timing, touch mapping through logical
    presentation, the IME for the name field, immersive mode, and the back gesture on Android 13+.
  - The upstream port's own Android work suggests the base path runs, e.g. its handling of SDL's orientation
    override and the IME on edit focus.

## Gotchas
1. **CMake: "external/vorbis does not contain a CMakeLists.txt"** (and the same for miniaudio). **Cause:** the
   PopLib fork's `external/discordrpc` submodule (EclipseMenu/discord-presence) no longer exists. The
   recursive clone aborts on it, leaving sibling submodules registered but empty. **Fix:** in `poplib`, run
   `git -c submodule.external/discordrpc.update=none submodule update --init --recursive --force`. The
   feature is off anyway.
2. **`fatal error: '../build/svn_version/svn_version.h' file not found` in libopenmpt `common/version.cpp`.**
   **Cause:** PopLib's `.gitignore` has `build/`, so vendoring libopenmpt 0.8.9 silently dropped its
   `build/svn_version/svn_version.h`. **Fix:** restore it from the official
   `libopenmpt-0.8.9+release.autotools.tar.gz`. The vendored tree is identical to that release apart from
   CRLF. Commit it with `git add -f`.
3. **The Android target looks complete but cannot work from git.** The manifest names an
   `InsaniquariumActivity` that isn't in the repo, no gradle setting packages the game files, and BASS's
   jniLibs were wired in. See Build step 3.
4. **Gradle: "The filename, directory name, or volume label syntax is incorrect".** **Cause:**
   `local.properties` is a Java .properties file, so `C:\Users\<you>\...` turns `\U` into an escape and mangles the
   SDK path. **Fix:** use forward slashes.
5. **`sdkmanager` prints a deprecation and `--licenses` does nothing** (cmdline-tools 23). **Fix:** use
   `android sdk install`. It downloads its own runtime on first use and collects metrics unless you pass
   `--no-metrics`.
6. **Phones: the on-screen keyboard would cover the game at launch.** **Cause:** PopLib calls
   `SDL_StartTextInput(window)` when it creates the window, for desktop text events. With no hardware keyboard,
   SDL's `SDL_HINT_ENABLE_SCREEN_KEYBOARD` "auto" shows the IME. ImGui's backend only stops text input it
   started itself, so nothing puts the keyboard away. **Fix:** skip the call on Android. EditWidget starts and
   stops text input on focus.
7. **Lifecycle events arrive too late to act on.** **Cause:** with `SDL_HINT_ANDROID_BLOCK_ON_PAUSE` (the
   default), Java's `nativePause` only queues a lifecycle event. The main thread handles it inside
   `SDL_PumpEvents`, then blocks in that same call until resume. So `SDL_EVENT_DID_ENTER_BACKGROUND` sits in
   the queue and the game reads it only after it returns; if Android kills it, never. OpenAL keeps mixing on
   its own thread meanwhile. **Fix:** do it in an `SDL_AddEventWatch` callback (SDL's own comment says so).
   Watchers run while the event is pushed, on the main thread and between frames.
8. **The back button reaches native code as a key, not as `onBackPressed`.** `SDLSurface.onKey` consumes
   `KEYCODE_BACK` and sends `SDLK_AC_BACK`. The game ignores Escape and the AC_BACK name maps to nothing, so
   back did nothing at all. Trapping it and giving it a game meaning is up to the port. `SDL_SendAndroidBackButton()`
   asks for the system default.
9. **Status and navigation bars stay visible.** **Cause:** PopLib starts windowed unless the display is too
   small for 640×480, and a phone display never is. **Fix:** force fullscreen on Android (immersive mode),
   with `mForceFullscreen` so the Options checkbox can't undo it.
10. **"Do you want to check for updates?" on the second launch.** PopCap's server is gone and the APK has no
    INTERNET permission. **Fix:** force `mDontUpdate` on Android after `partner.xml` is read. That also hides
    Options' Check Update button.
11. **Bash scripts break after a Python patch on Windows.** `pathlib.write_text` writes CRLF, and
    `.gitattributes` `eol=lf` only fixes the blob, not your working copy. Patch with bytes, or `sed -i 's/\r$//'`.
    Git Bash's `grep $'\r'` does not see the CRs; count them with `tr -cd '\r' | wc -c`.
12. **Scripted headless runs: the same update number doesn't always reach the same screen.** Board loading
    depends on wall time. A `back` at update 2000 once fired before the tank existed, and the next click
    dropped food instead of ticking a checkbox. Leave about 500 updates of slack after screen changes.
13. **The Steam copy's file names don't match `resources.xml` case** (all the `sounds/*.ogg` are upper case).
    Windows doesn't care; Android's asset manager does. Run `verify-assets.py --fix-case`. It also renames the
    alpha companions `resources.xml` never names.
14. **Widescreen: the Fold's inner screen is narrower than 4:3**, not wider: 2184×1968 is about 10:9. A
    "widen the tank" plan alone leaves it letterboxed top and bottom. The screen has to grow in whichever
    direction the display does. Here the extra height goes below the HUD as more floor, with the bottom row of
    text moved down to it.
15. **Mirroring the tank picture outward copies its glass panes into the middle of the scene,** and the big props
    repeat (two diving helmets). Mirror only the area between the panes, then draw the panes at the screen's
    edges.
16. **Qwen-Image-Edit treats grey padding as part of the picture.** "Extend into the grey areas" gave back the
    grey. Masked inpainting works: `SetLatentNoiseMask` over the VAE-encoded canvas, denoise 1.0, with the
    padding pre-filled by a blurred mirror for colour.
    - A strong structure in the middle (tank 6's tiki statue) still gets copied into the sides. Add "do not
      repeat ..." to the prompt and repaint a wider band (90 px) to hide the join.
    - Re-roll per picture: tank 5 needed "dark, murky", and one seed for tank 6 changed the palette entirely.
17. **Only draw a menu's margins.** Drawing the whole wide picture behind a menu erases what it draws over its
    own background (loading bar, text) on frames where the menu itself isn't redrawn.
18. **A literal reflection below a menu shows mirrored, readable buttons.** Fade it to black away from the game
    area so it reads as a glossy floor.

## Assets
- The launcher icon is composed at build time from the player's own `smallswim.gif` and `aquarium1.jpg` with
  Pillow.
- The wide pictures (six tanks; title, main menu and store) are generated locally from the player's own copy
  with Qwen-Image-Edit, see "Widescreen".
- The APK contains PopCap's files and these derivatives, so it is for the owner's own devices and must not be
  shared.

## Cost and time
About 4 hours of agent time in one session, about half of it on widescreen. The Android SDK, NDK and Gradle
downloads came to about 1.3 GB. The image work took 12 Qwen-Image-Edit runs at 50–110 s each, on the user's
RTX 4090.

## Open questions
- First run on a real device: GL context after a long background, OpenSL/AAudio through OpenAL Soft, the
  IME covering the name field (the dialog sits in the middle of a 4:3 frame), and the predictive-back
  gesture (`enableOnBackInvokedCallback` is unset, so key events are expected).
- Touch targets: coins are about 30 px at 640×480. On a 1080 p phone that's around 4.5 mm, which plays fine
  by tapping but may want a larger hit radius.
- On the Fold's inner screen held in portrait, the app is landscape-only, so Android letterboxes it until the
  device is turned. The screen logic already handles any shape (640×640 at most), so the orientation could be
  freed on near-square screens.
- The Fold7 cover screen's camera hole sits at one landscape edge, inside the widened tank.

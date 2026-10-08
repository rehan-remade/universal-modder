# Release process

A release is permitted only from a clean, reviewed exact commit. Creating this candidate locally does not
authorize a tag, GitHub Release, marketplace update, package publication, or deployment.

## Candidate gates

1. Record the commit and tree hashes; require a clean worktree.
2. Run `uv lock --check` and `uv sync --frozen --dev`.
3. Run `uv run --frozen ruff check um tests scripts examples/minecraft-gta5-passthrough/gta/install_passthrough.py`.
4. Run `uv run --frozen pytest --cov=um --cov-branch --cov-fail-under=53 -q`; account for every skip.
5. Run `uv run --frozen um kb check --index`, `python scripts/sync_skills.py --check`, and
   run `um publish check` against a clean, exact candidate export (not a developer checkout containing `.venv`).
6. Build from two clean immutable materializations with the lock-provided Hatchling and `SOURCE_DATE_EPOCH`; run
   `python scripts/verify_release_candidate.py <build-a> <build-b>`.
7. Install only the wheel in a clean environment and run every CLI help contract plus
   `scripts/verify_installed_package.py`.
8. Verify JSON/TOML/YAML parsing, manifest name/version parity, archive member safety, and exact artifact hashes.
9. Obtain independent security and QA reviews of the exact candidate bytes.
10. Run native Windows and WSL lanes when Windows process/input/registry/capture/install code changed. Run pinned
    ffmpeg/Blender and provider-contract lanes when those integrations changed.

## Publication gate

Publication requires a separately approved annotated tag, least-privileged protected release environment,
immutable action pins, artifact checksums, SBOM, provenance attestation, and post-publication readback of every
artifact/tag/marketplace target. Mutable external example dependencies (FFmpeg, ScriptHookV, ReShade, Gradle,
MSVC/JDK) must have independently reviewed version/digest evidence before an example bundle is called
reproducible.

Until those hosted controls and platform lanes are verified, the correct verdict is:

- local review candidate: eligible after all local gates pass;
- production release: hold / no-go.

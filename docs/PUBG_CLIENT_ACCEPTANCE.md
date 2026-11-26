# Verify in the PUBG client

Toolkit 1.0.0 includes offline preparation. Testing in the target PUBG UGC build is scheduled for the next release. The local validator checks the PUGC and the profile, and Blender shows the geometry from meshes. The tester observes map opening, collisions, materials, and re-saving in the client.

## Two test runs

1. Record the exact client build, platform, and date. Compare the files' SHA-256 hashes with `client-check.json`. Open copies of the maps from the kit.
2. Open `new/map.pugc` in the UGC editor. Check the positions and rotations of the two supports and bench in `cases.new.expect`. Check bench visibility between the supports, the route between them, and the materials. Save a copy from the client, reopen it, and record its SHA-256.
3. Open `imported/input.pugc`, then `imported/map.pugc`. Compare the named instance position in `cases.imported.expect`, adjacent objects, and settings. Save and reopen the result. Record the hash and observations about the saved changes.
4. Fill in `client.build`, `client.resaved_sha256`, `client.notes`, and `client.status` for each case. For a discrepancy, record the exact editor message, the step, the map SHA-256, and a link to a frame or log. If you need a fresh owner template, save it in the target client, record its SHA-256, and repeat preparation with `--template`.

For each map, record the validator result, what Blender showed, and what you observed in PUBG. The client version, package version, and hashes tie the report to the run.

## Prepare the test kit

The archived revision contains an original sample map with two benches. It already includes a rotation edit to one bench. To check an individual edit, the command below shifts a different named instance by 25 cm. Run it with the Toolkit installed. Pass the nine-mesh ZIP through `--meshes` for a Blender preview and supply the package's source commit through `--candidate-sha` if known.

```sh
mkdir -p "$UGC_WORK/acceptance-input"
revision=c3ab056057d9eb04f401839619bbd35641c863e4
for name in route.pugc route.pugc.json; do
  git -C "$UGC_TOOLKIT" show "$revision:examples/ugc_route/evidence/$name" > "$UGC_WORK/acceptance-input/$name"
done
python -B "$UGC_TOOLKIT/tools/prepare_client_check.py" \
  --source "$UGC_WORK/acceptance-input/route.pugc" --instance bench-east \
  --out "$UGC_WORK/client-acceptance"
```

`client-check.json` records the Toolkit version, map metadata version, profile, and SHA-256 hashes of maps, sidecars, and any user template. For the imported map, the preparation script reopens the output and checks record order, settings, and every other game record. [Issue #18](https://github.com/dokerrrrr/pugcblender/issues/18)

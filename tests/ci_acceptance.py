"""Run the documented workflows and verify release inputs and subprocess outcomes."""
import argparse
from hashlib import file_digest
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
CODEC_FILES = {
    "pugc-codec-client.js": "634e08caf8409b18493888b0c8e54c546aa47755bc54ddea61789cc0d1525399",
    "aes256-ecb.js": "eab01dd0019468387e1c6eea60912a353114a4bb0d64a2bef2e97ad89657538d",
}
MESH_SHA256 = "d9c28d2dd01faa2fc809815635e37019efcf0d8179994b1db6381254e754c5b5"
OPTIONAL = {
    "test_blender_extract.BlenderExtraction.test_evaluated_geometry",
    "test_codec_and_mesh.CodecTest.test_node_reads_and_rewrites_empty_and_single_object_maps",
    "test_codec_and_mesh.MeshTest.test_full_mesh_after_sample_and_material_sections",
    "test_machine_cli.MachineCliTest.test_blender_resource_and_usage_statuses",
    "test_machine_cli.MachineCliTest.test_blender_finding_has_exit_two_and_preserves_artifacts",
    "test_pugc_container.NodeContainerTest.test_python_node_python_round_trip",
    "test_pugc_container.NodeContainerTest.test_node_encodes_game_coordinates_that_python_reads_verbatim",
    "test_route_audit.RouteAuditTest.test_directed_join_measures_step_and_overlapping_surfaces",
    "test_route_audit.RouteAuditTest.test_one_hidden_tire_and_two_supports",
    "test_ugc_project.ProjectTest.test_real_gate_uses_renderable_meshes",
}


def run(*argv, cwd=ROOT, **kwargs):
    return subprocess.run(argv, cwd=cwd, check=True, **kwargs)


def git(*argv):
    return run("git", *argv, stdout=subprocess.PIPE, text=True).stdout.strip()


def digest(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_links():
    def slug(text):
        return "".join(c for c in text.strip().lower() if c.isalnum() or c in " -_").replace(" ", "-")

    issues = []
    paths = [ROOT / name for name in git("ls-files", "*.md").splitlines()]
    for file in paths:
        for target in re.findall(r"\]\(([^()\s]+)\)", file.read_text(encoding="utf-8")):
            destination = urlsplit(target)
            if destination.scheme or destination.netloc:
                continue
            linked = (file.parent / unquote(destination.path)).resolve() if destination.path else file
            if not linked.exists():
                issues.append(f"{file.relative_to(ROOT)}: missing link {target}")
            elif destination.fragment and linked.suffix.lower() == ".md":
                headings = re.findall(r"^#{1,6} +(.+)$", linked.read_text(encoding="utf-8"), re.MULTILINE)
                if unquote(destination.fragment) not in {slug(heading) for heading in headings}:
                    issues.append(f"{file.relative_to(ROOT)}: missing heading {target}")
    if issues:
        raise ValueError("\n".join(issues))


def unit_tests(work, *, strict):
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    discovered = set()
    pending = [suite]
    while pending:
        test = pending.pop()
        if isinstance(test, unittest.TestSuite):
            pending.extend(test)
        else:
            discovered.add(test.id())
    if strict:
        expected = OPTIONAL | {"test_ugc_storage.PublicationTest.test_ordinary_failure_restores_all_outputs"}
        if expected - discovered:
            raise ValueError(f"Required tests were not discovered: {sorted(expected - discovered)}")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    skipped = {test.id(): reason for test, reason in result.skipped}
    write_json(work / "unittest.json", {"tests_run": result.testsRun, "skipped": skipped,
                                        "failures": len(result.failures), "errors": len(result.errors)})
    if not result.wasSuccessful() or not result.testsRun or (skipped if strict else skipped.keys() - OPTIONAL):
        raise ValueError("Unit tests failed or skipped a required test")


def machine(work, name, *arguments, code=0, reason=None):
    result = subprocess.run([sys.executable, "-B", "-I", "-m", "pugc_toolkit", "--json", *arguments],
                            cwd=work, capture_output=True, text=True, timeout=240)
    (work / f"{name}.stdout").write_text(result.stdout, encoding="utf-8")
    (work / f"{name}.stderr").write_text(result.stderr, encoding="utf-8")
    data = json.loads(result.stdout)
    if data["exit_code"] != code or result.returncode != code or (
            reason and reason not in {row["code"] for row in data["diagnostics"]}):
        raise ValueError(f"{name}: expected exit {code} and {reason}, got {result.returncode}: {data}")
    return data


def readme_workflows(work):
    checkout_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"^```bash\n(.*?)^```", checkout_readme, re.MULTILINE | re.DOTALL)
    if len(blocks) != 2:
        raise ValueError("Expected the two runnable Bash examples in README")
    data = work / "Работа агента"
    env = {**os.environ, "UGC_WORK": str(data)}
    env.pop("PYTHONPATH", None)
    for block in blocks:
        run("bash", cwd=work, input=block, text=True, env=env)
    digests = set()
    for name in ("New Map", "Edit"):
        directory = data / name
        expected = digest(directory / "map.pugc")
        digests.add(expected)
        receipt = json.loads((directory / "map.pugc.json").read_bytes())
        check = json.loads((directory / "validation.json").read_bytes())["data"]
        if receipt["pugc_sha256"] != expected or not check["valid"] or check["pugc_sha256"] != expected:
            raise ValueError(f"Documented workflow failed: {name}")
    if len(digests) != 2:
        raise ValueError("The documented edit did not change the imported map")


def prepare_integration(work):
    from pugc_toolkit.resources import ASSET_DIR

    for tool in ("blender", "node", "openssl"):
        if shutil.which(tool) is None:
            raise ValueError(f"Required integration executable is missing: {tool}")
    versions = {"python": sys.version, "commit": git("rev-parse", "HEAD")}
    for tool, flag in (("blender", "--version"), ("node", "--version"), ("openssl", "version")):
        versions[tool] = run(tool, flag, capture_output=True, text=True).stdout.splitlines()[0]
    write_json(work / "versions.json", versions)
    mesh, source = work / "route-meshes.zip", work / "source.npz"
    machine(work, "prepare-meshes", "fetch-pack", "small", "--offline", "--out", mesh)
    if digest(mesh) != MESH_SHA256:
        raise ValueError("The pinned nine-mesh ZIP changed")
    codec = work / "codec"
    codec.mkdir(exist_ok=True)
    for name, expected in CODEC_FILES.items():
        path = codec / name
        if not path.is_file() or digest(path) != expected:
            supplied = ASSET_DIR / "codec" / name
            if not supplied.is_file() or digest(supplied) != expected:
                raise ValueError(f"Missing or invalid codec fixture: {supplied}")
            shutil.copyfile(supplied, path)
    with (work / "blender-source.log").open("w", encoding="utf-8") as log:
        run("blender", "-b", "-t", "2", "--python-exit-code", "1", "--python",
            ROOT / "examples/ugc_route/create_source.py", "--", work / "source.blend",
            cwd=work, stdout=log, stderr=subprocess.STDOUT)
    machine(work, "extract", "blender", "--blend", work / "source.blend", "--threads", "2", "extract",
            "--", "--out", source)
    run(sys.executable, "-B", ROOT / "examples/ugc_route/prepare.py", work, cwd=work)
    os.environ.update(UGC_TEST_MESHES=str(mesh), UGC_TEST_SOURCE_NPZ=str(source),
                      UGC_TEST_JS_CODEC=str(codec / "pugc-codec-client.js"))
    tracked = [mesh, source, work / "source.blend", *(codec / name for name in CODEC_FILES),
               *(work / name for name in ("route.pugc", "wrong-tower.pugc", "overpass.pugc"))]
    write_json(work / "inputs.json", {str(path.relative_to(work)): digest(path) for path in tracked})


def integration_cli(work):
    mesh = work / "route-meshes.zip"
    args = ("--project", "route.json", "--meshes", mesh, "--cameras", "Approach", "Alongside",
            "--strict", "--samples", "1")
    for name, expected in (("route", 0), ("wrong-tower", 2)):
        result = machine(work, name, "blender", "--threads", "2", "compare", "--", "source.npz",
                         f"{name}.pugc", *args, "--out", f"{name}-frames", code=expected,
                         reason="geometry_mismatch" if expected else None)
        report = json.loads(Path(result["artifacts"]["report"]).read_bytes())
        detected = [(row["landmark"], row["camera"], row["issue"]) for row in report["issues"]]
        wanted = [("Tower", camera, "side_changed") for camera in ("Approach", "Alongside")] if expected else []
        if detected != wanted or report["pugc_sha256"] != digest(work / f"{name}.pugc"):
            raise ValueError(f"Unexpected comparison findings for {name}: {detected}")
    direct = machine(work, "direct-compare", "blender", "--threads", "2", "compare", "--", "source.blend",
                     "route.pugc", "--project", "route.json", "--meshes", mesh, "--samples", "1",
                     "--out", "direct-frames")
    direct_report = json.loads(Path(direct["artifacts"]["report"]).read_bytes())
    extracted_report = json.loads((work / "route-frames" / "comparison.json").read_bytes())
    direct_cameras = {frame["camera"]: frame["matrix_world"] for frame in direct_report["frames"]}
    if (set(direct_cameras) != {"Approach", "Alongside", "Exit"}
            or any(direct_cameras[frame["camera"]] != frame["matrix_world"] for frame in extracted_report["frames"])
            or any(not Path(frame).is_file() for key in ("source_frames", "result_frames")
                   for frame in direct["artifacts"][key])):
        raise ValueError("Direct Blender comparison did not render the matching source cameras")
    partial = work / "incomplete-meshes.zip"
    with ZipFile(mesh) as source, ZipFile(partial, "w") as archive:
        for name in source.namelist():
            if name != "bp-mesh/16087.bin.gz":
                archive.writestr(name, source.read(name))
    result = machine(work, "partial-audit", "blender", "--threads", "2", "audit", "--", "overpass.pugc",
                     "--project", "overpass.json", "--meshes", partial, "--strict", "--out", "partial-audit.json",
                     code=4, reason="mesh_missing")
    if result["data"]["geometry_check"]["status"] != "partial":
        raise ValueError("Missing mesh did not produce partial audit coverage")

    receipt = json.loads((work / "route.pugc.json").read_bytes())
    receipt["pugc_sha256"] = "0" * 64
    write_json(work / "broken-receipt.json", receipt)
    machine(work, "broken-pair", "validate", "route.pugc", "--receipt", "broken-receipt.json",
            code=1, reason="invalid_map")
    paths = [work / name for name in ("route.pugc", "route.pugc.json")]
    original = [digest(path) for path in paths]
    machine(work, "write-failure", "build", "route.json", "route.pugc", "--raw-json",
            "missing-directory/raw.json", code=5, reason="file_operation_failed")
    if original != [digest(path) for path in paths]:
        raise ValueError("A failed build changed a published pair")


def main():
    sys.path.insert(0, str(ROOT))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layer", choices=("quick", "integration", "documentation"))
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    if work.is_relative_to(ROOT):
        parser.error("Choose a work directory outside the checkout")
    work.mkdir(parents=True, exist_ok=True)
    def checkout_state():
        return {"status": git("status", "--porcelain", "--untracked-files=all"),
                "ignored": git("ls-files", "--others", "--ignored", "--exclude-standard")}

    original = checkout_state()
    check_links()
    strict = args.layer == "integration"
    if strict:
        prepare_integration(work)
        integration_cli(work)
    else:
        readme_workflows(work)
    if args.layer != "documentation":
        unit_tests(work, strict=strict)
    current = checkout_state()
    write_json(work / "checkout.json", {"before": original, "after": current, "unchanged": current == original})
    if current != original or os.environ.get("CI") and any(current.values()):
        raise ValueError("Checkout is dirty after CI checks")


if __name__ == "__main__":
    main()

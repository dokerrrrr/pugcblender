"""Prepare two original UGC acceptance cases and record offline evidence."""
import argparse
from hashlib import file_digest, sha256
import json
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def cli(directory, label, *arguments):
    result = subprocess.run(["pugc", "--json", *arguments], cwd=directory, capture_output=True, check=False)
    (directory / f"{label}.json").write_bytes(result.stdout)
    if result.stderr:
        (directory / f"{label}.stderr").write_bytes(result.stderr)
    result.check_returncode()
    report = json.loads(result.stdout)
    if report["exit_code"] != 0:
        raise ValueError(report["diagnostics"])
    return report["data"]


def build_case(directory, meshes):
    built = cli(directory, "build", "build", "project.json", "map.pugc")
    checked = cli(directory, "validation", "validate", "map.pugc")
    binary = digest(directory / "map.pugc")
    if not checked["valid"] or built["pugc_sha256"] != binary or checked["pugc_sha256"] != binary:
        raise ValueError(f"Invalid published map in {directory}")
    images = []
    if meshes is not None:
        for view in ("iso", "top"):
            image = f"{view}.png"
            cli(directory, f"preview-{view}", "blender", "--threads", "2", "preview", "--", "--pugc",
                "map.pugc", "--meshes", meshes, "--out", image, "--view", view)
            images.append(image)
    return {"map": "map.pugc", "pugc_sha256": binary, "receipt": "map.pugc.json",
            "receipt_sha256": digest(directory / "map.pugc.json"),
            "objects": checked["objects"], "build_version": checked["buildVersion"],
            "profile": checked["profile"], "profile_revision": checked["profile_revision"],
            "images_from_blender": images, "client": {"status": "awaiting_client", "build": None,
                                                       "resaved_sha256": None, "notes": []}}


def new_case(directory, template, meshes):
    options = ("--template", template) if template else ()
    cli(directory, "init", "init", "project.json", "--name", "Toolkit acceptance – gate", *options)
    for name, x, yaw in (("west-post", -2, 0), ("east-post", 2, 90)):
        cli(directory, name, "place", "project.json", name, "12005", "--at", str(x), "0", "1.5",
            "--yaw", str(yaw), "--assembly", "Gate")
    cli(directory, "bench", "place", "project.json", "bench", "16052", "--at", "0", "4", "0",
        "--assembly", "Gate")
    info = build_case(directory, meshes)
    info["template_sha256"] = digest(template) if template else None
    info["expect"] = {"positions_m": {"west-post": [-2, 0, 1.5], "east-post": [2, 0, 1.5], "bench": [0, 4, 0]},
                      "yaw_deg": {"west-post": 0, "east-post": 90, "bench": 0},
                      "check": "Pass between the posts and verify visibility of the bench."}
    return info


def imported_case(directory, source, instance_id, meshes):
    shutil.copyfile(source, directory / "input.pugc")
    receipt = source.with_suffix(source.suffix + ".json")
    if receipt.is_file():
        shutil.copyfile(receipt, directory / "input.pugc.json")
    cli(directory, "import", "import", "input.pugc", "project.json")
    project = directory / "project.json"
    original = project.read_bytes()
    before = json.loads(original)
    instances = {row["id"]: row for row in before["instances"]}
    placement = instances[instance_id]["transform"]["translation"]
    at = [placement[axis] / 100 for axis in "xyz"]
    at[0] += 0.25
    request = {"schema": 1, "base_sha256": sha256(original).hexdigest(), "operations": [
        {"op": "update", "id": instance_id, "fields": {"at_m": at}}
    ]}
    write_json(directory / "request.json", request)
    preview = cli(directory, "plan", "edit", project, "request.json", "--dry-run")
    applied = cli(directory, "edit", "edit", project, "request.json")
    if preview["result_sha256"] != applied["result_sha256"]:
        raise ValueError("The saved project does not match its preview")
    info = build_case(directory, meshes)
    cli(directory, "reopen", "import", "map.pugc", "reopened.json")
    after = json.loads((directory / "reopened.json").read_bytes())
    if before["game"] != after["game"] or list(instances) != [row["id"] for row in after["instances"]]:
        raise ValueError("The rebuilt map changed settings or instance order")
    changed = [row["id"] for row in after["instances"]
               if row["game_original"] != instances[row["id"]]["game_original"]]
    if changed != [instance_id]:
        raise ValueError(f"Expected only {instance_id!r}, changed {changed}")
    info.update(input="input.pugc", input_sha256=digest(directory / "input.pugc"),
                input_receipt_sha256=digest(directory / "input.pugc.json") if receipt.is_file() else None,
                expect={"changed_instance": instance_id, "position_m": at,
                        "settings_preserved": True, "other_records_preserved": len(instances) - 1})
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Existing original UGC map")
    parser.add_argument("--instance", required=True, help="Stable ID of the object to move")
    parser.add_argument("--template", type=Path, help="Optional fresh PUGC v3 file from the target client")
    parser.add_argument("--meshes", type=Path, help="Meshes ZIP for optional Blender previews")
    parser.add_argument("--candidate-sha", help="Git revision from which the installed package was built")
    parser.add_argument("--out", type=Path, required=True, help="New acceptance directory outside checkout")
    args = parser.parse_args()
    output = args.out.resolve()
    if output.is_relative_to(ROOT):
        parser.error("Choose a directory outside checkout")
    output.mkdir(parents=True)
    new, imported = output / "new", output / "imported"
    new.mkdir()
    imported.mkdir()
    meshes = args.meshes.resolve() if args.meshes else None
    template = args.template.resolve() if args.template else None
    version = cli(output, "version", "--version")["version"]
    environment = {"os": platform.platform(), "python": platform.python_version()}
    if meshes is not None:
        environment["blender"] = subprocess.check_output(["blender", "--version"], text=True).splitlines()[0]
        environment["mesh_zip_sha256"] = digest(meshes)
    protocol = {"schema": 1, "toolkit_version": version, "candidate_sha": args.candidate_sha,
                "status": "awaiting_client", "offline_environment": environment,
                "cases": {"new": new_case(new, template, meshes),
                          "imported": imported_case(imported, args.source.resolve(), args.instance, meshes)}}
    write_json(output / "client-check.json", protocol)
    shutil.copyfile(ROOT / "docs/PUBG_CLIENT_ACCEPTANCE.md", output / "CLIENT_TEST.md")
    print(output / "client-check.json")


if __name__ == "__main__":
    main()

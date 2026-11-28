"""Inspect and install pinned asset packs in a user-owned directory."""
import errno
from hashlib import file_digest, sha256
from http.client import HTTPException
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile, ZipInfo

from . import cli_protocol as cli
from .base_level import ISLAND_NAME, ISLAND_URL, base_level_candidates, inspect_base_level
from .resources import ASSET_CACHE, ASSET_DIR, CATALOG, MESHES, ROOT, TEXTURES, asset_candidates, default_asset
from .ugc_storage import install_staged, lock_outputs, output_paths

FULL_REVISION = "9068475a93cbd05293ae9379ed380ed0ce8e54a8"
SMALL_HASHES = {
    10048: "c82eb0efdae49e4e7bdd167f50091532fd9d9311b0def130a3a37d8ededf09ec",
    10053: "9d78615280d830f2f3e9097a264ae90db9d946e9edf227ab960ca1d8fcfa5dcf",
    12005: "95e8837478e9f675812430f11ace351a66727a18aa482df0e80697aae41393a7",
    13003: "7813e6334f2f37fee7f8d48bf228be92b02e135c9c09594876180b37f43b6a14",
    15006: "b483f9bb9c37d4a24665aa468c89dd2d044cc951146ea520755c5a48e9a57cf5",
    16052: "f5598319b6dc195702d6a3ab04333b61493de6898635ec69af06459169282079",
    16087: "17aedde2bec137820ae3d70c036a000c63bcfeaab6ddfefa967be7f625d0060b",
    16180: "6ac72429d884c6964c386029dfe32a38b544283b95fd362597202399486a0ed4",
    16197: "d9e2ac275b4afae7876949123f508a45281bf4efe5240580b0ce6e1f02ad2433",
}
SMALL_ENTRIES = {f"bp-mesh/{oid}.bin.gz": digest for oid, digest in SMALL_HASHES.items()}
FILENAMES = {"small": "route-meshes.zip", "full-meshes": MESHES.name, "full-textures": TEXTURES.name,
             "island": ISLAND_NAME}
FULL_KINDS = ("full-meshes", "full-textures")
FULL_RESOURCES = (*FULL_KINDS, "island")
PUBLIC_URLS = {kind: f"https://media.githubusercontent.com/media/dokerrrrr/pugcblender/{FULL_REVISION}/assets/{FILENAMES[kind]}"
               for kind in FULL_KINDS} | {"island": ISLAND_URL}
FULL_HASH_KEYS = {"full-meshes": "models_zip_sha256", "full-textures": "textures_zip_sha256"}
MANIFEST = CATALOG / "pack_contents.json"
LFS_MARKER = b"version https://git-lfs.github.com/spec/v1"


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _inspect_names(names, kind, manifest):
    files = len(names)
    if kind == "small":
        missing = sorted(SMALL_ENTRIES.keys() - set(names))
        if missing or files != len(SMALL_ENTRIES):
            return {"state": "pack_incomplete", "files": files, "missing_entries": missing}
        return {"state": "ok", "meshes": files}
    if kind == "full-textures":
        webp = sum(name.lower().endswith(".webp") for name in names)
        complete = files == manifest["texture_archive_file_count"] and webp == manifest["texture_webp_count"]
        return {"state": "ok" if complete else "pack_incomplete", "webp": webp, "files": files}

    meshes = {name[8:-7] for name in names if name.startswith("bp-mesh/") and name.endswith(".bin.gz")}
    cards = {name[8:-5] for name in names if name.startswith("bp-mesh/") and name.endswith(".json")}
    complete = len(meshes) == manifest["model_mesh_count"] and len(cards) == manifest["model_json_count"]
    state = "incomplete_pairs" if meshes != cards else "ok" if complete else "pack_incomplete"
    return {"state": state, "meshes": len(meshes), "cards": len(cards),
            "missing_cards": sorted(meshes - cards), "missing_meshes": sorted(cards - meshes)}


def inspect_pack(path, kind):
    if kind == "island":
        return inspect_base_level(path)
    path = Path(path).absolute()
    result = {"kind": kind, "path": str(path)}
    if not path.is_file():
        return {**result, "state": "archive_missing"}
    manifest = _manifest() if kind != "small" else None
    try:
        with path.open("rb") as stream:
            if stream.read(len(LFS_MARKER)).startswith(LFS_MARKER):
                return {**result, "state": "lfs_pointer"}
            with ZipFile(stream) as archive:
                result.update(_inspect_names(archive.namelist(), kind, manifest))
                if result["state"] == "incomplete_pairs":
                    return result
                if kind == "small" and result["state"] == "ok":
                    failed = [name for name, digest in SMALL_ENTRIES.items()
                              if sha256(archive.read(name)).hexdigest() != digest]
                    if failed:
                        result.update(state="hash_mismatch", mismatched_entries=failed)
            stream.seek(0)
            actual = file_digest(stream, "sha256").hexdigest()
            result["sha256"] = actual
    except (BadZipFile, RuntimeError, NotImplementedError):
        return {**result, "state": "archive_invalid"}
    if manifest is not None:
        expected = manifest[FULL_HASH_KEYS[kind]]
        result["expected_sha256"] = expected
        if actual != expected:
            result["state"] = "hash_mismatch"
    return result


def _suggestion(kind, path):
    path = Path(path)
    if kind == "small":
        if path.is_relative_to(ROOT):
            path = ASSET_CACHE / path.name
        command = ["pugc", "fetch-pack", kind, "--out", str(path), "--refresh",
                   "--archive", "/path/to/mesh-archive.zip"]
    elif not path.is_relative_to(ROOT) and path.name != FILENAMES[kind]:
        command = ["pugc", "fetch-pack", kind, "--out", str(path)]
    else:
        command = ["pugc", "fetch-pack", "full"]
        if path.parent != ASSET_CACHE and not path.is_relative_to(ROOT):
            command.extend(["--cache-dir", str(path.parent)])
    return shlex.join(command)


def _diagnostic(pack):
    state = pack["state"]
    detail = {
        "archive_missing": "ZIP archive is missing.",
        "base_level_missing": "The starting island GLB is missing.",
        "archive_invalid": "The file is not a readable ZIP archive.",
        "lfs_pointer": "Found a Git LFS pointer instead of the ZIP archive.",
        "incomplete_pairs": "The ZIP has unpaired meshes or catalog cards.",
        "pack_incomplete": "The ZIP does not contain the expected entries.",
        "hash_mismatch": "SHA-256 differs from the pinned content.",
    }[state]
    field = {"full-textures": "--textures", "island": "--base-level"}.get(pack["kind"], "--meshes")
    return cli.diagnostic(state, detail, _suggestion(pack["kind"], pack["path"]),
                          path=pack["path"], field=field)


def doctor(mode, cache, meshes=None, textures=None, base_level=None):
    directory = Path(cache).expanduser() if cache is not None else None
    packs = []
    if mode == "small":
        default = directory / FILENAMES["small"] if directory else default_asset(FILENAMES["small"])
        packs = [inspect_pack(meshes or default, "small")]
    if mode == "full":
        candidates = (base_level,) if base_level else (directory / ISLAND_NAME,) if directory else base_level_candidates()
        island = inspect_base_level(candidates[0])
        if island["state"] != "ok":
            for path in candidates[1:]:
                check = inspect_base_level(path)
                if check["state"] == "ok":
                    island = check
                    break
        packs = [inspect_pack(meshes or (directory / MESHES.name if directory else MESHES), "full-meshes"),
                 inspect_pack(textures or (directory / TEXTURES.name if directory else TEXTURES), "full-textures"),
                 island]
    verified = {pack["kind"] for pack in packs if pack["state"] == "ok"}
    data = {"mode": mode, "packs": packs,
            "features": {"catalog": True, "project": True, "route_geometry": bool({"small", "full-meshes"} & verified),
                         "full_geometry": "full-meshes" in verified, "textures": "full-textures" in verified,
                         "island": "island" in verified}}
    diagnostics = [_diagnostic(pack) for pack in packs if pack["state"] != "ok"]
    return cli.response(data, diagnostics=diagnostics, exit_code=cli.RESOURCE if diagnostics else 0)


def _write_small(staged, source):
    with Path(source).open("rb") as stream:
        if stream.read(len(LFS_MARKER)) == LFS_MARKER:
            raise cli.CliError(cli.RESOURCE, "lfs_pointer", "The input ZIP is a Git LFS pointer.",
                               "Pass the restored archive with --archive.", path=source, field="--archive")
    with ZipFile(source) as local, ZipFile(staged, "w") as output:
        for name, expected in SMALL_ENTRIES.items():
            with local.open(name) as mesh:
                data = mesh.read(8 * 1024 * 1024)
            if sha256(data).hexdigest() != expected:
                raise cli.CliError(cli.RESOURCE, "hash_mismatch", f"SHA-256 mismatch for {name}.",
                                   "Use a verified local archive.", path=source, field=name)
            output.writestr(ZipInfo(name), data)


def _fetch_lfs(checkout, kind, staged):
    filename = f"assets/{FILENAMES[kind]}"
    git = ["git", "-C", str(checkout)]
    pointer = subprocess.run([*git, "show", f"HEAD:{filename}"], check=True,
                             capture_output=True).stdout
    if not pointer.startswith(LFS_MARKER):
        raise ValueError("Pinned Git revision did not return a Git LFS pointer.")
    storage = staged.parent / "lfs"
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "0", "GIT_TERMINAL_PROMPT": "0"}
    with staged.open("wb") as output:
        subprocess.run([*git, "-c", f"lfs.storage={storage}", "lfs", "smudge", filename],
                       input=pointer, stdout=output, stderr=subprocess.PIPE, env=env, check=True)


def _lfs_remote(git):
    def read(args, *, check=True):
        return subprocess.run([*git, *args], check=check, capture_output=True, text=True).stdout.strip()

    ref = read(["symbolic-ref", "--quiet", "HEAD"], check=False)
    if ref.startswith("refs/heads/"):
        tracked = read(["config", "--get", f"branch.{ref.removeprefix('refs/heads/')}.remote"], check=False)
        if tracked:
            return tracked
    default = read(["config", "--get", "remote.lfsdefault"], check=False)
    if default:
        return default
    remotes = read(["remote"]).splitlines()
    return remotes[0] if len(remotes) == 1 else "origin" if remotes else "."


def _fetch_lfs_batch(checkout, kinds, storage):
    git = ["git", "-C", str(checkout)]
    include = ",".join(f"assets/{FILENAMES[kind]}" for kind in kinds)
    manifest = _manifest()
    objects = {}
    for kind in kinds:
        oid = manifest[FULL_HASH_KEYS[kind]]
        objects[kind] = storage / "objects" / oid[:2] / oid[2:4] / oid

    # An isolated object store keeps the checkout intact and lets us recover valid objects
    # from a batch in which another transfer failed.
    result = subprocess.run([*git, "-c", f"lfs.storage={storage}", "-c", "lfs.fetchrecentalways=false",
                             "lfs", "fetch", f"--include={include}", "--exclude=", "--", _lfs_remote(git),
                             "HEAD"], capture_output=True,
                            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    return objects, result.returncode


def _check_output_location(output, checkout, field):
    if output.is_relative_to(ROOT) or (checkout is not None and output.is_relative_to(Path(checkout).resolve())):
        raise cli.CliError(cli.USAGE, "invalid_arguments", "Choose an output outside the toolkit directory.",
                           f"Pass a user data path with {field}.", path=output, field=field)


def _local_archive(kind, output, checkout=None):
    if kind == "small":
        candidates = (ASSET_DIR / FILENAMES[kind], *asset_candidates(FILENAMES[kind]), MESHES)
        return next((path for path in candidates if path.is_file() and path.resolve() != output), None)
    candidates = base_level_candidates() if kind == "island" else asset_candidates(FILENAMES[kind])
    if checkout is not None:
        candidates = (Path(checkout) / "assets" / FILENAMES[kind], *candidates)
    return next((path for path in dict.fromkeys(candidates)
                 if path.resolve() != output and inspect_pack(path, kind)["state"] == "ok"), None)


def _cached_pack(kind, output, refresh):
    if not refresh:
        previous = inspect_pack(output, kind)
        if previous["state"] == "ok":
            return cli.response({"cache": "verified", "pack": previous}, artifacts={"archive": output})
    return None


def _download_error(output, returncode):
    detail = (f"Git or Git LFS exited with code {returncode}." if returncode else
              "Git LFS did not return the pinned archive.")
    return cli.CliError(cli.RESOURCE, "download_failed", detail,
                        "Check Git LFS access or pass a local ZIP with --archive.", path=output)


def _download_public(kind, staged, destination):
    url = PUBLIC_URLS[kind]
    print(f"Downloading {staged.name} …", file=sys.stderr)
    with staged.open("wb") as output:
        try:
            with urlopen(url, timeout=30) as response:
                shutil.copyfileobj(response, output, length=1024 * 1024)
        except (OSError, HTTPException) as exc:
            if isinstance(exc, OSError) and exc.errno in {errno.ENOSPC, errno.EDQUOT}:
                raise
            raise cli.CliError(cli.RESOURCE, "download_failed", f"Could not download {url}: {exc}",
                               "Check access to the public download and retry.", path=destination) from exc


def _install_pack(kind, output, *, archive=None, checkout=None, downloaded=None, offline=False):
    if archive is None and downloaded is None and (offline or kind == "small"):
        code = "base_level_missing" if kind == "island" else "archive_missing"
        raise cli.CliError(cli.RESOURCE, code, "No verified local copy was found.",
                           _suggestion(kind, output) if not offline else "Supply the local file or rerun without --offline.",
                           path=output, field="--archive")
    with TemporaryDirectory(prefix=".pugc-pack-", dir=output.parent) as directory:
        staged = Path(directory) / output.name
        try:
            if kind == "small":
                _write_small(staged, archive)
            elif archive is not None:
                shutil.copyfile(archive, staged)
            elif downloaded is not None:
                shutil.move(downloaded, staged)
            elif checkout is not None:
                _fetch_lfs(checkout, kind, staged)
            else:
                _download_public(kind, staged, output)
        except KeyError as exc:
            raise cli.CliError(cli.RESOURCE, "pack_incomplete", str(exc), "Pass a ZIP with all nine meshes.",
                               path=archive, field="--archive") from exc
        except subprocess.CalledProcessError as exc:
            raise _download_error(output, exc.returncode) from exc
        verification = inspect_pack(staged, kind)
        verification["path"] = str(Path(archive).absolute() if archive is not None else output)
        if verification["state"] != "ok":
            return cli.response({"pack": verification}, diagnostics=[_diagnostic(verification)],
                                exit_code=cli.RESOURCE)
        with staged.open("r+b") as stream:
            os.fsync(stream.fileno())
        install_staged(staged, output)
    verification["path"] = str(output)
    return cli.response({"cache": "installed", "pack": verification}, artifacts={"archive": output})


def fetch(kind, output, *, archive=None, checkout=None, offline=False, refresh=False):
    output = Path(output).resolve()
    _check_output_location(output, checkout, "--out")
    output.parent.mkdir(parents=True, exist_ok=True)
    (output,) = output_paths((output,), inputs=(archive,))
    with lock_outputs((output,)):
        cached = _cached_pack(kind, output, refresh)
        if cached is not None:
            return cached
        if archive is None:
            archive = _local_archive(kind, output, checkout)
        output_paths((output,), inputs=(archive,))
        return _install_pack(kind, output, archive=archive, checkout=checkout, offline=offline)


def fetch_full(cache_dir, *, checkout=None, offline=False, refresh=False):
    directory = Path(cache_dir).expanduser().resolve()
    _check_output_location(directory, checkout, "--cache-dir")
    paths = tuple((directory / FILENAMES[kind]).resolve() for kind in FULL_RESOURCES)
    for path in paths:
        _check_output_location(path, checkout, "--cache-dir")
    directory.mkdir(parents=True, exist_ok=True)
    output_paths(paths)
    outputs = dict(zip(FULL_RESOURCES, paths, strict=True))
    results = {}
    with lock_outputs(paths), TemporaryDirectory(prefix=".pugc-pack-", dir=directory) as staging:
        for kind, path in outputs.items():
            cached = _cached_pack(kind, path, refresh)
            if cached is not None:
                results[kind] = cached
        missing = [kind for kind in FULL_RESOURCES if kind not in results]
        archives = {kind: _local_archive(kind, outputs[kind], checkout) for kind in missing}
        output_paths(paths, inputs=archives.values())
        downloaded, returncode = {}, 0
        batch = [kind for kind in FULL_KINDS if kind in missing and archives[kind] is None]
        if batch and checkout is not None and not offline:
            try:
                downloaded, returncode = _fetch_lfs_batch(checkout, batch, Path(staging) / "lfs")
            except subprocess.CalledProcessError as exc:
                returncode = exc.returncode
                downloaded = dict.fromkeys(batch)
        for kind in missing:
            path = outputs[kind]
            try:
                source = downloaded.get(kind)
                if kind in downloaded and (source is None or not source.is_file()):
                    raise _download_error(path, returncode)
                results[kind] = _install_pack(kind, path, archive=archives.get(kind),
                                              downloaded=source, offline=offline)
            except cli.INPUT_ERRORS as exc:
                results[kind] = cli.from_error(exc, path=path)
    packs, artifacts, diagnostics = {}, {}, []
    exit_code = 0
    for kind in FULL_RESOURCES:
        result = results[kind]
        packs[kind] = result["data"]
        if "archive" in result["artifacts"]:
            artifacts[kind.removeprefix("full-")] = result["artifacts"]["archive"]
        diagnostics.extend(result["diagnostics"])
        exit_code = exit_code or result["exit_code"]
    return cli.response({"packs": packs}, artifacts=artifacts, diagnostics=diagnostics, exit_code=exit_code)


def add_doctor_arguments(parser):
    parser.add_argument("--mode", choices=("base", "small", "full"), default="base")
    parser.add_argument("--cache-dir", type=Path, help="Directory with user-owned asset packs")
    parser.add_argument("--meshes", type=Path, help="Override the selected geometry ZIP")
    parser.add_argument("--textures", type=Path, help="Override the texture ZIP in full mode")
    parser.add_argument("--base-level", type=Path, help="Override the island GLB in full mode")


def add_fetch_arguments(parser):
    parser.add_argument("kind", choices=(*FILENAMES, "full"))
    outputs = parser.add_mutually_exclusive_group()
    outputs.add_argument("--out", type=Path, help="Output file for a single resource")
    outputs.add_argument("--cache-dir", type=Path, help="Override the shared cache used for the full download")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--archive", type=Path, help="Read from a local ZIP or island GLB")
    sources.add_argument("--checkout", type=Path, help="Use a local checkout as the source for the full ZIPs")
    parser.add_argument("--offline", action="store_true", help="Use an existing cache or a local archive")
    parser.add_argument("--refresh", action="store_true", help="Verify and stage an explicitly requested refresh")


def run(args, parser):
    try:
        if args.command == "doctor":
            if (args.mode == "base" and args.meshes or
                    args.mode != "full" and (args.textures or args.base_level)):
                parser.error("Select --mode small for the small mesh ZIP or --mode full for both full ZIPs and the island")
            result = doctor(args.mode, args.cache_dir, args.meshes, args.textures, args.base_level)
        elif args.kind == "full":
            if args.out is not None or args.archive is not None:
                parser.error("Use --cache-dir to choose the full cache directory")
            result = fetch_full(args.cache_dir or ASSET_CACHE, checkout=args.checkout,
                                offline=args.offline, refresh=args.refresh)
        else:
            if args.out is None:
                parser.error("Use --out for a single resource")
            if args.kind not in FULL_KINDS and args.checkout is not None:
                parser.error("--checkout is only used for the full ZIPs")
            result = fetch(args.kind, args.out, archive=args.archive, checkout=args.checkout,
                           offline=args.offline, refresh=args.refresh)
    except cli.INPUT_ERRORS as exc:
        result = cli.from_error(exc)
    if args.json:
        return result
    print(json.dumps(result if result["diagnostics"] else result["data"], ensure_ascii=False, indent=2))
    return result["exit_code"]

"""Build and inventory the distributable Toolkit from a clean Git revision."""
import argparse
import ast
from email.parser import BytesParser
import gzip
from hashlib import file_digest
from importlib.metadata import version
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/dokerrrrr/pugcblender"
EXCLUDED_PREFIXES = {"assets", "examples", "optional", "projects", "reference", "tests", "tools"}
EXCLUDED_SUFFIXES = {".blend", ".bsp", ".glb", ".mp4", ".npz", ".pugc", ".vmf", ".webp", ".zip"}


def git(*arguments):
    return subprocess.check_output(["git", "-C", ROOT, *arguments], text=True).strip()


def read_version(source):
    module = ast.parse((source / "pugc_toolkit/__init__.py").read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(key, ast.Name) and key.id == "__version__"
                                                for key in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("Could not find the Toolkit version")


def normalize_sdist(distribution, epoch):
    """Set timestamps on the compressed source archive and each of its members."""
    staged = distribution.with_name(distribution.name + ".tmp")
    with tarfile.open(distribution, "r:gz") as source, staged.open("wb") as stream:
        with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=epoch) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as target:
                for entry in sorted(source.getmembers(), key=lambda row: row.name):
                    member = tarfile.TarInfo(entry.name)
                    member.mtime = epoch
                    member.type = entry.type
                    member.size = entry.size
                    member.mode = entry.mode
                    if entry.isfile():
                        with source.extractfile(entry) as contents:
                            target.addfile(member, contents)
                    elif entry.isdir():
                        target.addfile(member)
                    else:
                        raise ValueError(f"Unexpected sdist entry type: {entry.name}")
    staged.replace(distribution)


def artifact(distribution, expected_version, excluded_paths):
    if distribution.suffix == ".whl":
        with ZipFile(distribution) as archive:
            files = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
            metadata = next(name for name in files if name.endswith(".dist-info/METADATA"))
            data = {name: archive.read(name) for name in files}
    else:
        with tarfile.open(distribution, "r:gz") as archive:
            files = [entry.name for entry in archive.getmembers() if entry.isfile()]
            metadata = next(name for name in files if len(PurePosixPath(name).parts) == 2
                            and PurePosixPath(name).name == "PKG-INFO")
            data = {}
            for name in files:
                with archive.extractfile(name) as stream:
                    data[name] = stream.read()
    if len(files) != len(set(files)):
        raise ValueError(f"Duplicate files in {distribution.name}")
    package = BytesParser().parsebytes(data[metadata])
    if (package["Version"] != expected_version or package["Name"] != "pubg-ugc-toolkit"
            or f"-{expected_version}" not in distribution.name):
        raise ValueError(f"Unexpected package name or version in {distribution.name}")
    for name, payload in data.items():
        path = PurePosixPath(name)
        parts = path.parts if distribution.suffix == ".whl" else path.parts[1:]
        if (path.is_absolute() or ".." in parts or parts[0] in EXCLUDED_PREFIXES
                or path.suffix.lower() in EXCLUDED_SUFFIXES or ".pugc." in path.name.lower()
                or any(location in payload for location in excluded_paths)):
            raise ValueError(f"Unexpected release content: {name}")
    with distribution.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    return {"name": distribution.name, "sha256": digest, "bytes": distribution.stat().st_size,
            "files": sorted(files)}


def build_release(reference, output):
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("The checkout must be clean for a candidate build")
    commit = git("rev-parse", "--verify", "--end-of-options", f"{reference}^{{commit}}")
    epoch = int(git("show", "-s", "--format=%ct", commit))
    if output.is_relative_to(ROOT) or output.exists():
        raise ValueError("Choose a new output directory outside checkout")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".pugc-release-", dir=output.parent) as directory:
        work = Path(directory)
        source, dist = work / "source", work / "dist"
        source.mkdir()
        dist.mkdir()
        tree = subprocess.check_output(["git", "-C", ROOT, "archive", commit])
        exported = work / "source.tar"
        exported.write_bytes(tree)
        with tarfile.open(exported) as archive:
            archive.extractall(source, filter="data")
        environment = {**os.environ, "SOURCE_DATE_EPOCH": str(epoch)}
        subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--outdir", dist, source],
                       env=environment, check=True)
        wheel, = dist.glob("*.whl")
        sdist, = dist.glob("*.tar.gz")
        normalize_sdist(sdist, epoch)
        expected_version = read_version(source)
        excluded_paths = [os.fsencode(path) for path in (ROOT, source)]
        artifacts = [artifact(path, expected_version, excluded_paths) for path in (wheel, sdist)]
        manifest = {"schema": 1, "commit": commit, "source_url": f"{REPOSITORY}/tree/{commit}",
                    "version": expected_version, "source_date_epoch": epoch,
                    "builder": {"python": platform.python_version(), "build": version("build"),
                                "setuptools": version("setuptools")}, "artifacts": artifacts}
        (dist / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (dist / "SHA256SUMS").write_text("".join(f"{row['sha256']}  {row['name']}\n" for row in artifacts),
                                       encoding="ascii")
        for original, filename in (("CHANGELOG.md", "CHANGELOG.md"),
                                   ("docs/RELEASE_PREFLIGHT.md", "RELEASE_NOTES.md")):
            note = (source / original).read_text(encoding="utf-8")
            relative = PurePosixPath(original).parent
            note = re.sub(r"\]\(([^():]+\.md)\)",
                          lambda match: f"]({REPOSITORY}/blob/{commit}/{relative / match[1]})", note)
            (dist / filename).write_text(note, encoding="utf-8")
        dist.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD", help="Git commit to build")
    parser.add_argument("--out", type=Path, required=True, help="New directory for artifacts and SHA-256")
    args = parser.parse_args()
    try:
        result = build_release(args.ref, args.out.resolve())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(f"Toolkit {result['version']} from {result['commit']} → {args.out.resolve()}")


if __name__ == "__main__":
    main()

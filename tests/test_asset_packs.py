from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from pugc_toolkit import asset_packs
from pugc_toolkit.cli_protocol import CliError
from pugc_toolkit.ugc_project import main
from pugc_toolkit.ugc_storage import PublicationError, lock_outputs

ROOT = Path(__file__).resolve().parents[1]


def archive(path, entries):
    with ZipFile(path, "w") as output:
        for name, data in entries.items():
            output.writestr(name, data)


class AssetPacksTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="Ресурсы ")
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)

    def cli(self, *args, code=0):
        result = subprocess.run([sys.executable, "-B", "-m", "pugc_toolkit", "--json", *args],
                                cwd=self.work, env={**os.environ, "PYTHONPATH": str(ROOT)},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, code, (result.stdout, result.stderr))
        return json.loads(result.stdout)

    def test_base_and_full_diagnose_missing_pointer_unpaired_and_hash(self):
        meshes, textures = (self.work / asset_packs.FILENAMES[kind] for kind in ("full-meshes", "full-textures"))
        pointer = asset_packs.LFS_MARKER + b"\noid sha256:" + b"0" * 64 + b"\nsize 134\n"
        for path in (meshes, textures):
            path.write_bytes(pointer)
        self.assertTrue(self.cli("doctor", "--mode", "base")["data"]["features"]["project"])
        result = self.cli("doctor", "--mode", "full", "--cache-dir", self.work, code=4)
        self.assertEqual([row["code"] for row in result["diagnostics"]], ["lfs_pointer", "lfs_pointer"])
        self.assertIn("pugc fetch-pack", result["diagnostics"][0]["action"])
        textures.unlink()
        archive(meshes, {"bp-mesh/12005.bin.gz": b"mock"})
        result = self.cli("doctor", "--mode", "full", "--cache-dir", self.work, code=4)
        self.assertEqual([row["code"] for row in result["diagnostics"]], ["incomplete_pairs", "archive_missing"])
        self.assertEqual(result["data"]["packs"][0]["missing_cards"], ["12005"])
        archive(meshes, {"bp-mesh/12005.bin.gz": b"mock", "bp-mesh/12005.json": b"{}"})
        result = self.cli("doctor", "--mode", "full", "--cache-dir", self.work, code=4)
        self.assertEqual(result["data"]["packs"][0]["state"], "hash_mismatch")
        self.assertFalse(result["data"]["features"]["full_geometry"])

    def test_offline_cache_and_failed_refresh_preserve_working_files(self):
        entries = {"bp-mesh/12005.bin.gz": b"first", "bp-mesh/16052.bin.gz": b"second"}
        expected = {name: sha256(data).hexdigest() for name, data in entries.items()}
        source = self.work / "source.zip"
        output = self.work / "nested" / "cache.zip"
        archive(source, entries)
        with patch.object(asset_packs, "SMALL_ENTRIES", expected):
            cached = asset_packs.fetch("small", output, archive=source, offline=True)
            self.assertEqual(cached["data"]["cache"], "installed")
            previous = output.read_bytes()
            source_bytes = source.read_bytes()
            self.assertEqual(asset_packs.fetch("small", output, offline=True)["data"]["cache"], "verified")
            with patch.multiple(asset_packs, ASSET_DIR=self.work / "absent", MESHES=self.work / "absent.zip"):
                with self.assertRaises(CliError) as raised:
                    asset_packs.fetch("small", output, refresh=True)
                self.assertEqual(raised.exception.diagnostic["code"], "archive_missing")
            default = self.work / asset_packs.FILENAMES["small"]
            default.write_bytes(source_bytes)
            with patch.object(asset_packs, "ASSET_DIR", self.work):
                restored = asset_packs.fetch("small", output, refresh=True)
                self.assertEqual(restored["data"]["cache"], "installed")
                self.assertEqual(previous, output.read_bytes())
            with lock_outputs((output,)):
                with self.assertRaises(PublicationError):
                    asset_packs.fetch("small", output, archive=source, refresh=True)
            self.assertEqual(source.read_bytes(), source_bytes)
            with ZipFile(source) as contents:
                missing = self.work / "incomplete.zip"
                archive(missing, {"bp-mesh/12005.bin.gz": contents.read("bp-mesh/12005.bin.gz")})
            with self.assertRaises(CliError) as raised:
                asset_packs.fetch("small", output, archive=missing, offline=True, refresh=True)
            self.assertEqual(raised.exception.diagnostic["code"], "pack_incomplete")
            damaged = self.work / "damaged.zip"
            archive(damaged, {**entries, "bp-mesh/16052.bin.gz": b"wrong"})
            with self.assertRaises(CliError) as raised:
                asset_packs.fetch("small", output, archive=damaged, offline=True, refresh=True)
            self.assertEqual(raised.exception.diagnostic["code"], "hash_mismatch")
            self.assertEqual(previous, output.read_bytes())
            self.assertEqual(list(output.parent.glob(".pugc-pack-*")), [])

    def test_full_fetch_batches_missing_packs_and_reuses_verified_results(self):
        kinds = asset_packs.FULL_KINDS
        names = {kind: asset_packs.FILENAMES[kind] for kind in kinds}
        source = self.work / "source"
        source.mkdir()
        archive(source / names["full-meshes"], {"bp-mesh/12005.bin.gz": b"mesh", "bp-mesh/12005.json": b"{}"})
        archive(source / names["full-textures"], {"texture.webp": b"texture"})
        payloads = {kind: (source / name).read_bytes() for kind, name in names.items()}
        manifest = {
            "model_mesh_count": 1, "model_json_count": 1, "texture_archive_file_count": 1, "texture_webp_count": 1,
            **{key: sha256(payloads[kind]).hexdigest() for kind, key in asset_packs.FULL_HASH_KEYS.items()},
        }
        cache = self.work / "cache"

        def stage_batch(command, **kwargs):
            storage = Path(next(value.split("=", 1)[1] for value in command if value.startswith("lfs.storage=")))
            requested = command[command.index("fetch") + 1].removeprefix("--include=").split(",")
            self.assertEqual(command[-2:], ["origin", asset_packs.FULL_REVISION])
            for kind, name in names.items():
                if f"assets/{name}" not in requested or kind == "full-textures" and interrupted:
                    continue
                oid = manifest[asset_packs.FULL_HASH_KEYS[kind]]
                path = storage / "objects" / oid[:2] / oid[2:4] / oid
                path.parent.mkdir(parents=True)
                path.write_bytes(payloads[kind])
            return subprocess.CompletedProcess(command, 2 if interrupted else 0)

        interrupted = True
        with (patch.object(asset_packs, "_manifest", return_value=manifest),
              patch.object(asset_packs, "_lfs_remote", return_value="origin"),
              patch.object(asset_packs.subprocess, "run", side_effect=stage_batch) as request):
            stdout = StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(main(["--json", "fetch-pack", "full", "--checkout", str(ROOT),
                                       "--cache-dir", str(cache)]), 4)
            first = json.loads(stdout.getvalue())
            request.assert_called_once()
            self.assertIn(f"--include=assets/{names[kinds[0]]},assets/{names[kinds[1]]}", request.call_args.args[0])
            self.assertEqual(first["artifacts"], {"meshes": str(cache / names["full-meshes"])})
            self.assertEqual(first["diagnostics"][0]["code"], "download_failed")

            request.reset_mock()
            offline = asset_packs.fetch_full(cache, checkout=ROOT, offline=True)
            self.assertEqual(offline["exit_code"], 4)
            self.assertEqual(offline["diagnostics"][0]["code"], "archive_missing")
            request.assert_not_called()

            interrupted = False
            retry = asset_packs.fetch_full(cache, checkout=ROOT)
            self.assertEqual(retry["exit_code"], 0)
            self.assertEqual(retry["data"]["packs"]["full-meshes"]["cache"], "verified")
            request.assert_called_once()
            self.assertIn(f"--include=assets/{names['full-textures']}", request.call_args.args[0])
            for kind, name in names.items():
                self.assertEqual((cache / name).read_bytes(), payloads[kind])

            request.reset_mock()
            self.assertEqual(asset_packs.fetch_full(cache, checkout=ROOT)["exit_code"], 0)
            request.assert_not_called()

            interrupted = True
            refresh = asset_packs.fetch_full(cache, checkout=ROOT, refresh=True)
            self.assertEqual(refresh["exit_code"], 4)
            self.assertEqual((cache / names["full-textures"]).read_bytes(), payloads["full-textures"])

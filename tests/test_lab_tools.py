"""Prepare Blender inputs from a synthesized BSP face and VMF brush."""
from importlib.util import find_spec
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from pugc_toolkit.ugc_project import build, new_project, place, transform

ROOT = Path(__file__).resolve().parents[1]


def write_bsp(path):
    data = bytearray(8 + 64 * 16 + 4)
    struct.pack_into("<4si", data, 0, b"VBSP", 20)
    face = bytearray(56)
    struct.pack_into("<HBBihhh", face, 0, 0, 0, 1, 0, 4, 0, -1)
    lumps = {
        2: bytes(32), 3: struct.pack("<12f", 0, 0, 0, 16, 0, 0, 16, 24, 0, 0, 24, 0),
        6: bytes(72), 7: face, 12: struct.pack("<8H", 0, 1, 1, 2, 2, 3, 3, 0),
        13: struct.pack("<4i", 0, 1, 2, 3), 43: b"test/face\x00", 44: bytes(4),
    }
    for index, contents in lumps.items():
        struct.pack_into("<4i", data, 8 + index * 16, len(data), len(contents), 0, 0)
        data.extend(contents)
    path.write_bytes(data)


def write_vmf(path):
    planes = [
        "(0 0 0) (0 24 12) (0 0 12)", "(16 0 0) (16 0 12) (16 24 12)",
        "(0 0 0) (16 0 12) (16 0 0)", "(0 24 0) (16 24 0) (16 24 12)",
        "(0 0 0) (16 24 0) (0 24 0)", "(0 0 12) (0 24 12) (16 24 12)",
    ]
    sides = [f'side\n{{\n"plane" "{plane}"\n"material" "test/face"\n}}\n' for plane in planes]
    path.write_text('world\n{\nsolid\n{\n"id" "1"\n' + "".join(sides) + '}\n}\n', encoding="utf8")


@unittest.skipUnless(find_spec("numpy") and shutil.which("openssl"), "NumPy and OpenSSL required for the lab")
class LabToolsTest(unittest.TestCase):
    def test_blender_lab_prepares_direct_source_layers(self):
        import numpy as np

        with TemporaryDirectory(prefix="Лаборатория ") as directory:
            work = Path(directory)
            bsp, vmf, pugc = (work / name for name in ("face.bsp", "brush.vmf", "map.pugc"))
            write_bsp(bsp)
            write_vmf(vmf)
            project = new_project("Lab fixture")
            place(project, "post", 12005, transform((1, 2, 3)), "Lab fixture", "near")
            build(project, pugc)
            meshes = work / "meshes.zip"
            with ZipFile(meshes, "w") as archive:
                archive.writestr("bp-mesh/12005.bin.gz", b"mesh bytes")
                archive.writestr("bp-mesh/12005.json", "{}")

            output = work / "lab inputs"
            proc = subprocess.run([sys.executable, "-B", ROOT / "tools/prepare_overpass_blender_lab.py",
                                   "--bsp", bsp, "--vmf", vmf, "--reference", pugc,
                                   "--mesh-zip", meshes, "--out", output],
                                  cwd=work, capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, (proc.stdout, proc.stderr))
            report = json.loads((output / "overpass_lab_inputs.json").read_text())
            self.assertEqual(report["source"], {"bsp": bsp.name, "vmf": vmf.name, "pugc": pugc.name})
            self.assertEqual(report["bsp"]["triangles"], 2)
            self.assertEqual(report["vmf"]["triangles"], 12)
            self.assertEqual(report["reference"]["props"][0]["t"], {"x": 99900, "y": 200, "z": 300})
            self.assertEqual(report["asset_ids"], [12005])
            with np.load(output / "overpass_source_surfaces.npz", allow_pickle=False) as surfaces:
                self.assertEqual(surfaces["bsp"].shape, (6, 10))
                self.assertEqual(surfaces["vmf"].shape, (36, 10))
            with ZipFile(output / "overpass_ugc_meshes.zip") as archive:
                self.assertEqual(archive.read("bp-mesh/12005.bin.gz"), b"mesh bytes")

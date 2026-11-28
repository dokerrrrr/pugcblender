"""Blender 5.x renderer with REAL UGC meshes, not placeholder cubes.
blender -b --python blender_preview_pugc.py -- --pugc map.pugc --meshes ugc_meshes.zip --out preview.png
Use --save-blend filename.blend to save reviewed scene separately (not in this kit).
"""
import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import bpy
from mathutils import Vector
import numpy as np

from . import cli_protocol as cli
from .base_level import (
    ISLAND_BOUNDS_M, ISLAND_Z_RANGE_M, WATER_Z_M, add_arguments, environment_metadata, resolve_base_level,
)
from .blender_base_level import add_base_level
from .blender_render import GameMaterials, configure_cycles, mesh, overview_camera
from .mesh_library import MeshLibrary
from .resources import MESHES, TEXTURES
from .ugc_project import read_with_receipt

def args(machine=False):
    tail=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser_type = cli.MachineParser if machine else argparse.ArgumentParser
    p = parser_type(prog="pugc blender preview" if machine else None, description=__doc__)
    p.add_argument('--pugc',required=True);p.add_argument('--meshes',default=MESHES)
    p.add_argument('--out',required=True);p.add_argument('--save-blend',default=None)
    p.add_argument('--view',choices=['iso','top','side'],default='iso')
    p.add_argument("--mode", choices=("geometry", "textured"), default="geometry")
    p.add_argument("--textures", type=Path, default=TEXTURES, help="Native texture ZIP for textured mode")
    p.add_argument("--bindings", type=Path, help="Confirmed material-path → ZIP-entry JSON")
    p.add_argument("--samples", type=int, default=18, help="Cycles sample count in textured mode")
    p.add_argument("--frame", choices=("objects", "island", "all"), default="objects",
                   help="Frame the placed objects, the island, or both (default: %(default)s)")
    p.add_argument("--receipt")
    p.add_argument("--origin-x-cm", type=float)
    add_arguments(p)
    options = p.parse_args(tail)
    if options.samples < 1:
        p.error("--samples must be positive")
    cli.archive_argument(options, p, "--meshes")
    if options.mode == "textured":
        cli.archive_argument(options, p, "--textures")
    return options, p

def main(*, machine=False):
    a, parser = args(machine)
    if a.mode == "geometry":
        return render_preview(a, parser, machine, None)
    with ZipFile(a.textures) as archive, TemporaryDirectory() as directory:
        materials = GameMaterials(archive, a.bindings, Path(directory), pack_images=bool(a.save_blend))
        return render_preview(a, parser, machine, materials)


def render_preview(a, parser, machine, materials):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    data, receipt = read_with_receipt(a.pugc, a.receipt, a.origin_x_cm)
    objects=data.get('objects',[])
    ids=sorted({int(x['objectId']) for x in objects})
    with MeshLibrary(a.meshes, authoring=True) as library:
        missing = set(ids) - library.ids
        if missing:
            if machine:
                return cli.response(diagnostics=[cli.missing_mesh(a.meshes, object_id=oid) for oid in sorted(missing)],
                                    exit_code=cli.RESOURCE)
            raise KeyError(f"Missing real mesh IDs in zip: {sorted(missing)}")
        meshes = {}
        for oid in ids:
            geometry = library.geometry(oid)
            meshes[oid] = (materials.mesh(oid, geometry) if materials else
                           mesh(f"Actual_UGC_Mesh_{oid}", geometry.vertices, geometry.triangles, None, [], None))
    island = resolve_base_level(a, parser)
    scene = bpy.context.scene
    group = bpy.data.collections.new("PUGC_RECONSTRUCTED_REAL_MESHES")
    scene.collection.children.link(group)
    for index, entry in enumerate(objects):
        oid = entry["objectId"]
        placement = entry["spawnTransform"]
        obj = bpy.data.objects.new(f"UGC_{index:04d}_ID_{oid}", meshes[oid])
        group.objects.link(obj)
        obj.location = tuple(placement["translation"][axis] / 100 for axis in "xyz")
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = tuple(placement["rotation"][axis] for axis in "wxyz")
        obj.scale = tuple(placement["scale3D"][axis] for axis in "xyz")
        obj.color = (.60, .62, .66, 1) if oid == 12016 else (.47, .52, .57, 1)

    origin_x_cm = receipt["origin_x_cm"]
    datum_x = 2 * origin_x_cm / 100
    x0, y0, x1, y1 = ISLAND_BOUNDS_M
    island_bounds = [(datum_x - x1, y0, WATER_Z_M), (datum_x - x0, y1, ISLAND_Z_RANGE_M[1])]
    frame = a.frame if objects else "island"
    bounds = []
    if frame in ("objects", "all"):
        bpy.context.view_layer.update()
        bounds.extend(tuple(obj.matrix_world @ Vector(corner))
                      for obj in group.objects for corner in obj.bound_box)
    if frame in ("island", "all"):
        bounds.extend(island_bounds)
    bounds = np.asarray(bounds)
    add_base_level(scene, island, origin_x_cm=origin_x_cm)
    if materials:
        configure_cycles(scene, a.samples)
    else:
        scene.render.engine='BLENDER_WORKBENCH'
        scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT'
        scene.display.shading.show_cavity=False;scene.display.shading.show_shadows=False
        scene.world.color=(.17,.2,.24)
    scene.render.resolution_x=1250;scene.render.resolution_y=880;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    camera_data = bpy.data.cameras.new("QA_Camera")
    cam = bpy.data.objects.new("QA_Camera", camera_data)
    scene.collection.objects.link(cam)
    aspect = scene.render.resolution_x / scene.render.resolution_y
    cam.data.type = 'ORTHO'
    cam.matrix_world, cam.data.ortho_scale, cam.data.clip_end = overview_camera(bounds, a.view, aspect)
    scene.camera = cam
    output = bpy.path.abspath(a.out) if machine else a.out
    scene.render.filepath=a.out;bpy.ops.render.render(write_still=True)
    if a.save_blend:bpy.ops.wm.save_as_mainfile(filepath=a.save_blend,compress=True)
    if machine:
        # Blender appends the image extension when the selected name has none.
        preview = output if output.lower().endswith(".png") else output + ".png"
        artifacts = {"preview": preview}
        if a.save_blend:
            artifacts["blend"] = bpy.data.filepath
        data = {"objects": len(objects), "object_ids": ids, "frame": frame,
                "environment": environment_metadata()}
        if materials:
            data.update(material_coverage=materials.coverage(), result_materials=materials.rows)
        return cli.response(data, artifacts=artifacts)
    print(f'QA OK: {len(objects)} objects, IDs {ids}, file {a.out}')
    if materials:
        counts = materials.coverage()
        print(f'Textures applied to {counts["textured"]}/{counts["materials"]} materials '
              f'({counts["missing_bindings"]} missing bindings, {counts["image_issues"]} image issues).')
if __name__=='__main__':main()

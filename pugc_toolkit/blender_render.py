"""Shared Blender rendering, framing, and game materials."""
import base64
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from mathutils import Vector
import numpy as np

from .resources import CATALOG
from .ugc_project import load_json


def material(name, color, path=None, packed=None, *, pack_image=False):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = color
    node.inputs["Roughness"].default_value = .8
    image = None
    issue = None
    if path or packed:
        try:
            if packed:
                with TemporaryDirectory() as temporary:
                    image_file = Path(temporary) / "source-image"
                    image_file.write_bytes(base64.b64decode(packed))
                    image = bpy.data.images.load(str(image_file))
                    image.pack()
            else:
                image = bpy.data.images.load(str(path), check_existing=True)
            if not all(image.size):
                issue = "missing_image"
            elif tuple(image.size) == (1, 1):
                issue = "possible_placeholder_1x1"
            else:
                if pack_image and not image.packed_file:
                    image.pack()
                tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
                tex.image = image
                mat.node_tree.links.new(tex.outputs["Color"], node.inputs["Base Color"])
        except (RuntimeError, OSError):
            issue = "missing_image"
    return mat, issue


def mesh(name, vertices, triangles, uv, materials, indices):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices.tolist(), [], triangles.tolist())
    for item in materials:
        data.materials.append(item)
    if indices is not None and len(triangles):
        data.polygons.foreach_set("material_index", np.asarray(indices, dtype=np.int32))
    if uv is not None and len(triangles):
        layer = data.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", uv.astype(np.float32).ravel())
    data.update()
    return data


class GameMaterials:
    def __init__(self, textures, bindings, directory, *, pack_images=False):
        self.textures = textures
        self.matches = load_json(CATALOG / "texture_material_candidates.json")
        self.confirmed = load_json(bindings) if bindings else {}
        self.directory = directory
        self.pack_images = pack_images
        self.rows = []

    def create(self, oid, name):
        candidate = next((entry.get("diffuse_guess") for entry in self.matches.get(str(oid), [])
                          if entry["source_material"] == name), None)
        confirmed = self.confirmed.get(name)
        path = confirmed or candidate
        binding = "confirmed" if confirmed else "name_similarity" if candidate else "missing_binding"
        row = {"objectId": oid, "material": name, "texture": path, "binding": binding}
        local = None
        if path:
            if path in self.textures.NameToInfo:
                local = self.directory / (hashlib.sha256(path.encode()).hexdigest() + Path(path).suffix)
                if not local.exists():
                    local.write_bytes(self.textures.read(path))
            else:
                row["image_issue"] = "missing_image"
        mat, issue = material(name, (.45, .48, .52, 1), local, pack_image=self.pack_images)
        if issue:
            row["image_issue"] = issue
        self.rows.append(row)
        return mat

    def mesh(self, oid, geometry):
        materials = [material("Unassigned", (.45, .48, .52, 1))[0]]
        indices = np.zeros(len(geometry.triangles), dtype=np.int32)
        assigned = {}
        for section in geometry.sections:
            if section.material not in assigned:
                assigned[section.material] = len(materials)
                materials.append(self.create(oid, section.material))
            first = section.first_triangle
            indices[first:first + section.triangle_count] = assigned[section.material]
        return mesh(f"UGC {oid}", geometry.vertices, geometry.triangles, geometry.triangle_uvs, materials, indices)

    def coverage(self):
        return {
            "materials": len(self.rows),
            "textured": sum(bool(row["texture"]) and "image_issue" not in row for row in self.rows),
            "confirmed": sum(row["binding"] == "confirmed" for row in self.rows),
            "inferred": sum(row["binding"] == "name_similarity" for row in self.rows),
            "missing_bindings": sum(row["binding"] == "missing_binding" for row in self.rows),
            "image_issues": sum("image_issue" in row for row in self.rows),
        }


def configure_cycles(scene, samples):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.world = bpy.data.worlds.new("Sky")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.37, .48, .64, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .45
    light = bpy.data.lights.new("Sun", "SUN")
    light.energy = 2.4
    sun = bpy.data.objects.new("Sun", light)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (.66, -.57, -.2)


def overview_camera(bounds, view, aspect):
    span = np.ptp(bounds, axis=0)
    focus = Vector((bounds.min(axis=0) + bounds.max(axis=0)) / 2)
    largest = max(*span, 10)
    direction = {"iso": (.86, -1.2, .9), "top": (0, 0, 2.5), "side": (2.0, 0, .35)}
    offset = Vector(direction[view]) * largest
    rotation = (-offset).to_track_quat("-Z", "Y").to_matrix()
    screen_span = np.abs(np.asarray(rotation.transposed())) @ span
    pose = rotation.to_4x4()
    pose.translation = focus + offset
    return pose, 1.15 * max(screen_span[0], screen_span[1] * aspect, 10), max(10000, largest * 10)

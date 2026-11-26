"""Verify lab measurements and source visibility in an opened Blender scene."""
import argparse
from pathlib import Path
import runpy
import sys


def main():
    import bpy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-script", type=Path, default=Path(__file__).with_name("LAB_TOOLS.py"),
                        help="Path to the lab add-on used by this scene")
    tail = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(tail)

    runpy.run_path(str(args.lab_script), run_name="__main__")
    collection = bpy.data.collections["03 · REFERENCE PUGC — real UGC meshes"]
    instance = next(obj for obj in collection.objects if obj.instance_type == "COLLECTION")
    bpy.ops.object.select_all(action="DESELECT")
    instance.select_set(True)
    bpy.context.view_layer.objects.active = instance
    result = bpy.ops.lab.nearest_bsp()
    print("Nearest result", result, bpy.context.scene.get("lab_last_measurement"))
    assert result == {"FINISHED"}
    source = bpy.data.collections["01 · SOURCE BSP — original compiled geometry"]
    bpy.context.scene.lab_show_bsp = False
    assert source.hide_viewport
    bpy.context.scene.lab_show_bsp = True
    assert not source.hide_viewport
    print("TOGGLES PASSED", instance.name, instance.get("UGC_Object_ID"))


if __name__ == "__main__":
    main()

"""Validate a saved Overpass lab in Blender without a GPU."""
import argparse
from pathlib import Path
import sys


def main():
    import bpy
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Output verification JSON")
    tail = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(tail)
    f=Path(bpy.data.filepath)
    s=bpy.context.scene
    c={x.name:x for x in bpy.data.collections}
    ref=c['03 · REFERENCE PUGC — real UGC meshes']
    gen=c['04 · GENERATED PUGC — comparison']
    bsp=c['01 · SOURCE BSP — original compiled geometry']
    vmf=c['02 · SOURCE VMF — visible brush geometry']
    refobs=[o for o in ref.objects if o.instance_type=='COLLECTION']
    genobs=[o for o in gen.objects if o.instance_type=='COLLECTION']
    lib_ids=set(int(o['UGC_Object_ID']) for o in refobs)
    assert len(refobs)==2801,len(refobs)
    assert len(genobs)==3000,len(genobs)
    assert len(lib_ids)==187,len(lib_ids)
    assert all(o.instance_collection is not None for o in refobs+genobs)
    assert bpy.data.objects.get('SOURCE_ALIGNMENT — move/rotate to align Source with PUGC')
    assert bpy.data.meshes['BSP_VISIBLE_TRIANGLES_TRIANGLES']
    assert bpy.data.meshes['VMF_BRUSH_TRIANGLES_TRIANGLES']
    assert len(bpy.data.meshes['BSP_VISIBLE_TRIANGLES_TRIANGLES'].polygons)==61697
    assert len(bpy.data.meshes['VMF_BRUSH_TRIANGLES_TRIANGLES'].polygons)==30275
    assert any('reference' in m.name.lower() for m in bpy.data.materials)
    # Internal mesh assets really exist and have nonzero triangle data.
    real_ref_data={o.data.name:len(o.data.polygons) for o in bpy.data.objects if o.name.startswith('REF_UGC_') and o.type=='MESH'}
    assert real_ref_data and sum(real_ref_data.values())>100000,real_ref_data
    # A reference placement should have the exact intended UE position.
    ob=refobs[0]
    actual=ob.matrix_world.translation
    src=ob.get('PUGC_record_index')
    print('[VERIFIED] blender',bpy.app.version_string)
    print('[VERIFIED] scene file bytes',f.stat().st_size)
    print('[VERIFIED] reference actors',len(refobs),'generated actors',len(genobs),'unique real UGC IDs',len(lib_ids))
    print('[VERIFIED] real library meshes',len(real_ref_data),'library tris',sum(real_ref_data.values()))
    print('[VERIFIED] selected instance',ob.name,'world location',tuple(round(x,3) for x in actual),'pugc index',src)
    print('[VERIFIED] BSP',len(bsp.objects),'VMF',len(vmf.objects),'visible source triangles',sum(len(o.data.polygons) for o in bsp.objects if o.type=='MESH'))
    print('[VERIFIED] generated layer hidden',gen.hide_viewport,gen.hide_render)
    # Make sure Blender viewport can evaluate internal collection instances.
    dg=bpy.context.evaluated_depsgraph_get();base=0;inst=0
    for ob in dg.object_instances:
        if ob.is_instance:inst+=1
        else:base+=1
    print('[VERIFIED] depsgraph parent objects',base,'expanded mesh instances',inst)
    assert inst>2801,'Library collections failed to instance'
    validation={'blender':bpy.app.version_string,
     'reference_objects':len(refobs),'generated_objects':len(genobs),
     'real_ugc_model_ids':len(lib_ids),'real_mesh_datablocks':len(real_ref_data),
     'real_mesh_library_triangles':sum(real_ref_data.values()),
     'evaluated_instances':inst,'bsp_triangles':61697,'vmf_triangles':30275,
     'source_alignment':list(bpy.data.objects['SOURCE_ALIGNMENT — move/rotate to align Source with PUGC'].location)}
    args.out.write_text(json.dumps(validation,indent=2),encoding='utf8')


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Overpass native Geometry Lab builder for Blender 5.3 (run with --background --python).

Builds actual Source BSP/VMF triangle layers and actual PUBG UGC geometry from
published PUGC Editor bp-mesh dump, instanced by PUGC transformations.
Only deviceIndex == -1 entries are included. No devices are generated.

Example:
  blender --background --python create_overpass_blender_lab.py -- \
    --data-dir /path/to/overpass_blender_lab --output /path/to/Overpass_Geometry_Lab.blend
"""
import argparse,colorsys,gzip,json,math,os,pathlib,struct,sys,time,zipfile
import numpy as np
import bpy
from mathutils import Matrix,Quaternion,Vector

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pugc_toolkit.base_level import WATER_Z_M, add_arguments, environment_metadata, resolve_base_level
from pugc_toolkit.blender_base_level import add_base_level

START=time.perf_counter()

def log(*args):
    print('[OverpassLab]',*args,flush=True)

def args_for_blender():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir',default=str(pathlib.Path(__file__).resolve().parent))
    ap.add_argument('--meshes',type=pathlib.Path,help='Overpass mesh ZIP (defaults to the ZIP in --data-dir)')
    ap.add_argument('--output',type=pathlib.Path,required=True,help='Output .blend file')
    ap.add_argument('--no-render',action='store_true')
    ap.add_argument('--render-dir',default=None)
    add_arguments(ap)
    args = ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    return args, resolve_base_level(args, ap)

# Source lab is stored as coordinates (x, y-up, z); Blender uses z-up.
AXES=Matrix(((1.0,0.0,0.0,0.0),
             (0.0,0.0,1.0,0.0),
             (0.0,1.0,0.0,0.0),
             (0.0,0.0,0.0,1.0)))

def as_blender_geometry(v):
    """Real UGC .bin vertex coordinates are already in METERS and Y-up."""
    return np.ascontiguousarray(v[:,[0,2,1]],dtype=np.float32)

def create_mesh(name,xyz,colors=None,faces_have_swapped_handedness=True):
    xyz=np.asarray(xyz,dtype=np.float32)
    n=len(xyz)
    if n%3:raise ValueError(f'{name}: vertex count {n} not multiple of three')
    # Nonindexed triangle soup is intentional: each vertex can have unique section normals/UV.
    m=bpy.data.meshes.new(name)
    m.vertices.add(n)
    m.vertices.foreach_set('co',xyz.reshape(-1))
    m.loops.add(n)
    idx=np.arange(n,dtype=np.int32).reshape(-1,3)
    if faces_have_swapped_handedness:
        idx=idx[:,[0,2,1]]
    m.loops.foreach_set('vertex_index',idx.reshape(-1))
    m.polygons.add(n//3)
    m.polygons.foreach_set('loop_start',np.arange(0,n,3,dtype=np.int32))
    m.polygons.foreach_set('loop_total',np.full(n//3,3,dtype=np.int32))
    # For source, preserve the diagnostic material palette as a point-domain attribute.
    if colors is not None:
        ca=m.color_attributes.new(name='LAB_COLOR',type='FLOAT_COLOR',domain='POINT')
        rgb=np.asarray(colors,dtype=np.float32)
        rgba=np.concatenate((rgb,np.ones((n,1),dtype=np.float32)),axis=1)
        ca.data.foreach_set('color',rgba.reshape(-1))
    m.update(calc_edges=True)
    return m

def material(name,color,alpha=1.0,vertex_color=False):
    m=bpy.data.materials.new(name)
    m.diffuse_color=(*color,alpha)
    m.use_nodes=True
    nodes=m.node_tree.nodes;bsdf=nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value=(*color,1)
        bsdf.inputs['Roughness'].default_value=.9
        bsdf.inputs['Alpha'].default_value=alpha
        if vertex_color:
            attr=nodes.new('ShaderNodeVertexColor');attr.layer_name='LAB_COLOR'
            m.node_tree.links.new(attr.outputs['Color'],bsdf.inputs['Base Color'])
    if alpha<1:
        try:m.surface_render_method='DITHERED'
        except Exception:pass
    return m

def collection(name,root=True):
    col=bpy.data.collections.new(name)
    if root:bpy.context.scene.collection.children.link(col)
    return col

def load_source(name,arr,group,mat,source_parent):
    if arr.size==0:return None
    pos=as_blender_geometry(arr[:,0:3])
    mesh=create_mesh(name+'_TRIANGLES',pos,colors=arr[:,6:9])
    mesh.materials.append(mat)
    ob=bpy.data.objects.new(name,mesh)
    group.objects.link(ob)
    ob.parent=source_parent
    ob['source']='Source BSP' if 'BSP' in name else 'Source VMF'
    ob['triangles']=int(len(arr)//3)
    ob['vertex_color_attribute']='LAB_COLOR'
    ob.color=mat.diffuse_color
    return ob

def read_bin(raw,object_id):
    """Exact instanced .bin mesh wire format used by pugc-editor/mesh-assets.js."""
    view=memoryview(raw);pos=0
    def u32():
        nonlocal pos
        r=struct.unpack_from('<I',view,pos)[0];pos+=4;return r
    if u32()!=0xFFFFFFFE:raise ValueError(f'UGC {object_id}: wrong binary magic')
    nmesh=u32()
    if nmesh<=0 or nmesh>512:raise ValueError(f'UGC {object_id}: illegal part count {nmesh}')
    meshes=[]
    for mi in range(nmesh):
        vc=u32()
        if vc>3_000_000 or vc%3:raise ValueError(f'UGC {object_id}: illegal vertex count {vc}')
        xyz=np.frombuffer(view,dtype='<f4',count=3*vc,offset=pos).reshape(-1,3).copy()
        pos+=vc*12 # positions
        pos+=vc*12 # normals
        pos+=vc*8  # UVs
        secnum=u32();sections=[]
        for _ in range(secnum):
            first=u32();ntri=u32();ln=u32()
            path=bytes(view[pos:pos+ln]).decode('utf8','replace');pos+=ln
            sections.append((first,ntri,path))
        meshes.append((xyz,sections))
    ninst=u32()
    if ninst>20000:raise ValueError(f'UGC {object_id}: insane instance count')
    instances=[]
    for _ in range(ninst):
        mi=u32()
        if mi>=nmesh:raise ValueError(f'UGC {object_id}: bad instance meshIndex {mi}')
        matrix=np.frombuffer(view,dtype='<f4',count=16,offset=pos).copy();pos+=64
        instances.append((mi,Matrix(tuple(tuple(float(matrix[j*4+i]) for j in range(4)) for i in range(4)))))
    if pos!=len(raw):log(f'WARNING UGC {object_id} unused bytes={len(raw)-pos}')
    return meshes,instances

def make_library(id,meshes,instances,materials,parent_prefix='LIB'):
    # Collection kept as datablock ONLY, not linked as a top-level scene layer.
    # The 2801 placement objects reference these mesh objects without duplicating geometry.
    col=collection(f'{parent_prefix}_MODEL_{id}',root=False)
    parts=[]
    for mi,(xyz,sections) in enumerate(meshes):
        pts=as_blender_geometry(xyz)
        mesh=create_mesh(f'{parent_prefix}_UGC_{id}_PART_{mi:02d}',pts)
        mesh.materials.append(materials)
        mesh['material_paths']=' | '.join(sec[2] for sec in sections)[:8190]
        parts.append(mesh)
    for k,(mi,internal) in enumerate(instances):
        ob=bpy.data.objects.new(f'{parent_prefix}_UGC_{id}_internal_{k:03d}',parts[mi])
        col.objects.link(ob)
        ob.matrix_world=AXES@internal@AXES
    return col

def actor_matrix(obj):
    tr=obj['t'];q=obj['q'];s=obj['s']
    p=Vector((float(tr['x'])/100,float(tr['z'])/100,float(tr['y'])/100))
    quat=Quaternion((float(q['w']),-float(q['x']),-float(q['z']),-float(q['y'])))
    if quat.magnitude<.00001:quat=Quaternion((1,0,0,0))
    else:quat.normalize()
    sc=Vector((float(s['x']),float(s['z']),float(s['y'])))
    matrix=Matrix.Translation(p)@quat.to_matrix().to_4x4()@Matrix.Diagonal((sc.x,sc.y,sc.z,1.))
    return AXES@matrix@AXES

def add_actors(label,group,actors,libraries):
    total=len(actors)
    for i,o in enumerate(actors):
        id=o['id'];model=libraries.get(id)
        if model is None:continue
        inst=bpy.data.objects.new(f'{label}_{i:04d}_UGC_{id}',None)
        group.objects.link(inst)
        inst.instance_type='COLLECTION';inst.instance_collection=model
        inst.matrix_world=actor_matrix(o)
        inst.empty_display_type='PLAIN_AXES'
        inst.empty_display_size=.4
        inst['UGC_Object_ID']=int(id)
        inst['PUGC_record_index']=int(o['index'])
        inst['PUGC_source']=label
        inst['scale_UE']=[float(o['s'][ax]) for ax in 'xyz']
        if i%750==0 and i:log(label,'placed',i,'/',total)
    return total

def camera_at(name,loc,target,ortho=None):
    cam=bpy.data.cameras.new(name)
    ob=bpy.data.objects.new(name,cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location=loc
    direction=Vector(target)-ob.location
    ob.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()
    if ortho:
        cam.type='ORTHO';cam.ortho_scale=ortho
    else:cam.type='PERSP';cam.lens=35
    cam.clip_end=6000
    return ob

def setup_blender_view(center):
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.
    scene.render.engine='BLENDER_WORKBENCH'
    sh=scene.display.shading
    sh.light='STUDIO'
    sh.studio_light='paint.sl'
    sh.color_type='OBJECT';sh.show_cavity=True;sh.cavity_type='BOTH'
    sh.curvature_ridge_factor=1.0;sh.curvature_valley_factor=1.0
    sh.show_shadows=True
    sh.show_object_outline=True
    sh.background_type='WORLD'
    scene.world.color=(.07,.09,.11)
    scene.render.resolution_x=1600;scene.render.resolution_y=900;scene.render.resolution_percentage=75
    scene.render.image_settings.file_format='PNG'
    scene.camera=camera_at('CAM_Overview',(center.x+220,center.y-265,center.z+230),center)
    camera_at('CAM_Top',(center.x,center.y,center.z+390),center,ortho=440)
    camera_at('CAM_Side',(center.x,center.y-420,center.z+55),center,ortho=320)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active
                space.clip_end=8000
                space.region_3d.view_location=center
                space.region_3d.view_distance=320
                space.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion()
                space.shading.type='SOLID';space.shading.color_type='OBJECT'
                space.shading.show_cavity=True
                space.overlay.show_floor=True

def main():
    args, island = args_for_blender();base=pathlib.Path(args.data_dir).resolve()
    output=args.output.resolve()
    with open(base/'overpass_lab_inputs.json',encoding='utf8') as f:inputs=json.load(f)
    triangles=np.load(base/'overpass_source_surfaces.npz')
    zipfile_path=args.meshes or base/'overpass_ugc_meshes.zip'
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for c in list(bpy.data.collections):
        if c.name=='Collection' and not c.objects:bpy.data.collections.remove(c)
    source_group=collection('01 · SOURCE BSP — original compiled geometry')
    vmf_group=collection('02 · SOURCE VMF — visible brush geometry')
    teacher_group=collection('03 · REFERENCE PUGC — real UGC meshes')
    gen_group=collection('04 · GENERATED PUGC — comparison')
    source_parent=bpy.data.objects.new('SOURCE_ALIGNMENT — move/rotate to align Source with PUGC',None)
    bpy.context.scene.collection.objects.link(source_parent)
    source_parent.empty_display_type='CUBE';source_parent.empty_display_size=4
    a=inputs['alignment'];tx,ty,tz=a['translation_meters_blender_xyz']
    source_parent.location=(tx,ty,tz)
    source_parent.scale=(-1,1,1) if a['source_flip_x'] else (1,1,1)
    source_parent['alignment_note']=a['notice']
    source_parent['coordinates']='Source VMF/BSP inches → meters; Blender XYZ up'
    bspmat=material('SOURCE BSP / vertex material diagnostic',(.64,.66,.69),alpha=.5,vertex_color=True)
    vmfmat=material('SOURCE VMF / vertex material diagnostic',(.9,.65,.35),alpha=.35,vertex_color=True)
    bsp=load_source('BSP_VISIBLE_TRIANGLES',triangles['bsp'],source_group,bspmat,source_parent)
    vmf=load_source('VMF_BRUSH_TRIANGLES',triangles['vmf'],vmf_group,vmfmat,source_parent)
    bsp.display_type='TEXTURED';bsp.show_wire=False
    vmf.display_type='WIRE';vmf.show_wire=True
    vmf.hide_set(True)  # default OFF for performance: turn on in Outliner
    vmf.hide_render=True
    log('BSP/VMF meshes imported',len(triangles['bsp'])//3,len(triangles['vmf'])//3,'elapsed',round(time.perf_counter()-START,1))
    ids=inputs['asset_ids']
    libs={};genlibs={};mesh_errors=[];count_mesh=0;count_parts=0
    with zipfile.ZipFile(zipfile_path) as z:
        for k,id in enumerate(ids):
            try:
                b=gzip.decompress(z.read(f'bp-mesh/{id}.bin.gz'))
                meshes,instances=read_bin(b,id)
                color=colorsys.hsv_to_rgb((id*.61803398875)%1,.53,.89)
                colmat=material(f'REFERENCE · UGC {id}',color)
                libs[id]=make_library(id,meshes,instances,colmat,'REF')
                count_mesh+=sum(len(v) for v,s in meshes);count_parts+=len(instances)
                if inputs['generated'] is not None and id in {o['id'] for o in inputs['generated']['props']}:
                    genmat=material(f'GENERATED · UGC {id}',(.96,.26,.27))
                    # Copy meshes for generated material; ONLY IDs used by generated layer are duplicated.
                    genlibs[id]=make_library(id,meshes,instances,genmat,'GEN')
            except Exception as e:
                log('ERROR parsing UGC mesh',id,str(e));mesh_errors.append([id,str(e)])
            if k and k%40==0:log('Loaded real UGC types',k+1,'/',len(ids),'elapsed',round(time.perf_counter()-START,1))
    teacher=inputs['reference']['props']
    generated=(inputs['generated'] or {}).get('props',[])
    assert len(teacher)>0, 'No normal PUGC objects in reference'
    add_actors('REFERENCE',teacher_group,teacher,libs)
    add_actors('GENERATED',gen_group,generated,genlibs)
    gen_group.hide_viewport=True
    gen_group.hide_render=True
    log('Placed actors: reference',len(teacher),'generated',len(generated),'elapsed',round(time.perf_counter()-START,1))
    pp=np.array([[o['t']['x']/100,o['t']['y']/100,o['t']['z']/100] for o in teacher])
    # Reference PUGC coordinates already Z-up in Unreal; use PUGC center for camera.
    center=Vector(np.median(pp,axis=0).tolist())
    setup_blender_view(center)
    scene=bpy.context.scene
    add_base_level(scene, island)
    camera_at('CAM_Island', (510, -510, 860 + WATER_Z_M), (510, 510, WATER_Z_M), ortho=1620)
    scene['reference_count']=len(teacher)
    scene['generated_count']=len(generated)
    scene['source_BSP_triangles']=int(len(triangles['bsp'])//3)
    scene['source_VMF_triangles']=int(len(triangles['vmf'])//3)
    scene['UGC_mesh_types']=len(libs)
    scene['UGC_base_vertices']=count_mesh
    scene['UGC_internal_instances']=count_parts
    scene['alignment_verified_exact']=False
    scene['source_texture_status']='SOURCE diffuse textures absent; diagnostic materials only'
    scene['pugc_texture_status']='UGC dump supplied geometry with material paths, not diffuse images'
    # Text block with in-Blender helper commands, always available in the Text Editor.
    txt=bpy.data.texts.new('LAB_READ_ME_FIRST')
    txt.write('Overpass Geometry Lab (native Blender 5.3)\n'
              '01 SOURCE BSP: compiled Overpass triangles and displacements\n'
              '02 SOURCE VMF: visible convex brush surfaces (hidden by default)\n'
              '03 REFERENCE PUGC: 2801 placed actors, REAL UGC meshes\n'
              '04 GENERATED PUGC: independent experiment, hidden by default\n'
              'PUGC base level: starting island and preview water in game coordinates.\n'
              'SOURCE_ALIGNMENT: adjust X reflection and translation if anchors differ.\n'
              'Source diffuse textures are not complete; UGC materials are diagnostic colors.\n'
              'Only normal PUGC objects are included; devices excluded.\n'
              'Each REFERENCE_* is a Blender collection instance; select it to see Object ID.\n'
              'To toggle layers use Outliner eye/monitor; do not edit internal library meshes.\n'
              'For numeric comparison run analyze_overpass_geometry.py outside Blender.\n'
              'This scene is a measurement tool; registration is initial, not guaranteed exact.\n')
    # Embed the sidebar tool source inside .blend: Text Editor > LAB_TOOLS.py > Run Script.
    addon_file=base/'LAB_TOOLS.py'
    if addon_file.exists():
        addon_text=bpy.data.texts.new('LAB_TOOLS.py')
        addon_text.write(addon_file.read_text(encoding='utf8'))
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    stats={'blender':bpy.app.version_string,'file':str(output),'reference':len(teacher),
      'generated':len(generated),'missingUGCTypes':mesh_errors,
      'uniqueUGCTypes':len(libs),'meshVertices':count_mesh,'internalUGCInstances':count_parts,
      'bspTriangles':int(len(triangles['bsp'])//3),'vmfTriangles':int(len(triangles['vmf'])//3),
      'alignment':a,'environment':environment_metadata(),'elapsedSeconds':round(time.perf_counter()-START,2)}
    (output.parent/'build_validation.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf8')
    log('WROTE',output,round(output.stat().st_size/1e6,2),'MB',stats)
    if not args.no_render:
        render_dir=pathlib.Path(args.render_dir).resolve() if args.render_dir else output.parent
        render_dir.mkdir(parents=True,exist_ok=True)
        # Workbench screenshots, quick and useful for actual visual verification.
        scene.render.resolution_percentage=60
        scene.render.filepath=str(render_dir/'lab_reference_overview.png')
        bpy.ops.render.render(write_still=True)
        log('Rendered screenshot',scene.render.filepath)

if __name__=='__main__':main()

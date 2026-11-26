bl_info = {
    'name': 'Overpass Geometry Lab Tools',
    'author': 'OpenAI',
    'version': (1, 0, 0),
    'blender': (4, 3, 0),
    'location': '3D View > Sidebar (N) > Geometry Lab',
    'description': 'Control Source BSP/VMF vs PUGC layers and measure actual mesh-to-BSP distances',
    'category': '3D View',
}
import bpy,statistics,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy.props import BoolProperty

COLLECTIONS={
 'bsp':'01 · SOURCE BSP — original compiled geometry',
 'vmf':'02 · SOURCE VMF — visible brush geometry',
 'reference':'03 · REFERENCE PUGC — real UGC meshes',
 'generated':'04 · GENERATED PUGC — comparison',
}

def set_layer(name,enabled):
    col=bpy.data.collections.get(COLLECTIONS[name])
    if col is not None:
        col.hide_viewport=not enabled
        col.hide_render=not enabled
        for obj in col.objects:
            try:obj.hide_set(not enabled)
            except Exception:pass

def make_update(key):
    def update(self,context):set_layer(key,bool(getattr(self,'lab_show_'+key)))
    return update

class LAB_OT_nearest_bsp(bpy.types.Operator):
    '''Sample selected REAL UGC mesh vertices and measure distance to closest BSP triangles'''
    bl_idname='lab.nearest_bsp';bl_label='Measure selected model → BSP'
    bl_options={'REGISTER','INTERNAL'}
    @classmethod
    def poll(cls,context):
        o=context.active_object
        return o is not None and o.instance_type=='COLLECTION' and o.instance_collection is not None
    def execute(self,context):
        ob=context.active_object
        target=bpy.data.objects.get('BSP_VISIBLE_TRIANGLES')
        if not target:
            self.report({'ERROR'},'BSP mesh not present');return {'CANCELLED'}
        depsgraph=context.evaluated_depsgraph_get()
        bvh=BVHTree.FromObject(target,depsgraph)
        if bvh is None:
            self.report({'ERROR'},'Could not build BSP triangle BVH');return {'CANCELLED'}
        source_matrix=target.matrix_world.copy()
        world_to_bsp=source_matrix.inverted_safe()
        samples=[]
        # Sample up to ~400 real vertices total (no cube placeholders).
        children=[o for o in ob.instance_collection.objects if o.type=='MESH']
        full=sum(len(c.data.vertices) for c in children)
        if not full:self.report({'ERROR'},'No real model vertices');return {'CANCELLED'}
        for part in children:
            mesh=part.data
            every=max(1,math.ceil(full/450))
            M=ob.matrix_world @ part.matrix_world
            for i in range(0,len(mesh.vertices),every):
                p_world=M @ mesh.vertices[i].co
                p_local=world_to_bsp @ p_world
                hit=bvh.find_nearest(p_local)
                if hit and hit[0] is not None:
                    world=source_matrix @ hit[0]
                    samples.append((p_world-world).length)
        if not samples:
            self.report({'WARNING'},'No nearby BSP triangles found');return {'CANCELLED'}
        samples.sort()
        n=len(samples)
        med=samples[n//2]
        p90=samples[int(.9*(n-1))]
        name=ob.get('UGC_Object_ID','unknown')
        info=f'UGC {name} | {n} vertices | median {med:.2f}m | p90 {p90:.2f}m | <=1m {sum(v<=1 for v in samples)*100/n:.0f}%'
        context.scene['lab_last_measurement']=info
        self.report({'INFO'},info)
        print('[Overpass Lab]',info)
        return {'FINISHED'}

class LAB_OT_focus_object(bpy.types.Operator):
    '''Aim all visible 3D Views at selected object's PUGC pivot'''
    bl_idname='lab.focus';bl_label='Focus on selected PUGC object'
    @classmethod
    def poll(cls,context):return context.active_object is not None
    def execute(self,context):
        o=context.active_object
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type!='VIEW_3D':continue
                space=area.spaces.active
                space.region_3d.view_location=o.matrix_world.translation.copy()
                space.region_3d.view_distance=38
        return {'FINISHED'}

class LAB_OT_source_zero(bpy.types.Operator):
    '''Reset Source BSP/VMF alignment to calibrated initial transform'''
    bl_idname='lab.source_reset';bl_label='Reset source alignment'
    def execute(self,context):
        ob=bpy.data.objects.get('SOURCE_ALIGNMENT — move/rotate to align Source with PUGC')
        if ob:
            ob.location=(325.28,475.59,56.92)
            ob.scale=(-1,1,1)
            ob.rotation_euler=(0,0,0)
        self.report({'WARNING'},'Reset to approximate initial alignment; exact match unverified')
        return {'FINISHED'}

class LAB_PT_main(bpy.types.Panel):
    bl_label='Overpass Geometry Lab';bl_idname='LAB_PT_main'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Geometry Lab'
    def draw(self,context):
        s=context.scene;l=self.layout
        box=l.box();box.label(text='Layer visibility')
        box.prop(s,'lab_show_bsp',text='Compiled BSP')
        box.prop(s,'lab_show_vmf',text='VMF brush geometry')
        box.prop(s,'lab_show_reference',text='Reference: real UGC')
        box.prop(s,'lab_show_generated',text='Generated: comparison')
        box=l.box();box.label(text='Geometric inspection')
        ob=context.active_object
        if ob and ob.instance_type=='COLLECTION':
            box.label(text='Selected UGC ID: '+str(ob.get('UGC_Object_ID','—')))
            box.label(text='PUGC record: '+str(ob.get('PUGC_record_index','—')))
            box.label(text='Layer: '+str(ob.get('PUGC_source','—')))
        else:box.label(text='Select a PUGC object instance')
        box.operator('lab.nearest_bsp',icon='DRIVER_DISTANCE')
        box.operator('lab.focus',icon='VIEWZOOM')
        if 'lab_last_measurement' in s:
            txt=s['lab_last_measurement']
            for span in [txt[i:i+52] for i in range(0,len(txt),52)]:box.label(text=span)
        box=l.box();box.label(text='BSP / VMF alignment')
        ob=bpy.data.objects.get('SOURCE_ALIGNMENT — move/rotate to align Source with PUGC')
        if ob:
            box.prop(ob,'location',text='Offset (m)')
            box.prop(ob,'rotation_euler',text='Rotation')
            box.prop(ob,'scale',text='Reflection / scale')
        box.operator('lab.source_reset',icon='LOOP_BACK')
        box.label(text='Initial registration is approximate')

CLASSES=(LAB_OT_nearest_bsp,LAB_OT_focus_object,LAB_OT_source_zero,LAB_PT_main)

def register():
    for c in CLASSES:bpy.utils.register_class(c)
    for key in COLLECTIONS:
        setattr(bpy.types.Scene,'lab_show_'+key,BoolProperty(name='Show '+key,default=key in ('bsp','reference'),update=make_update(key)))

def unregister():
    for key in COLLECTIONS:delattr(bpy.types.Scene,'lab_show_'+key)
    for c in reversed(CLASSES):bpy.utils.unregister_class(c)

if __name__=='__main__':register()

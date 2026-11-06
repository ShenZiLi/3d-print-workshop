"""Run with Blender --background --factory-startup --python build_frame.py."""
import bpy
import bmesh
import math
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
MM = 0.001
scene = bpy.context.scene
# Only the isolated factory-startup scene is cleared.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'MILLIMETERS'
scene.unit_settings.scale_length = 1

def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

model = collection('01 | Picture Frame')
art = collection('02 | Artwork')
studio = collection('03 | Studio and Cameras')
refs = collection('04 | Reference')

def move(obj, coll):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    return obj

def material(name, color, roughness=.5, paper=False):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = roughness
    if paper:
        n = m.node_tree.nodes.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = 180
        b = m.node_tree.nodes.new('ShaderNodeBump')
        b.inputs['Strength'].default_value = .18
        b.inputs['Distance'].default_value = .000045
        m.node_tree.links.new(n.outputs['Fac'], b.inputs['Height'])
        m.node_tree.links.new(b.outputs['Normal'], p.inputs['Normal'])
    return m

ivory = material('Warm ivory | satin frame', (.78, .72, .61), .32)
boardmat = material('Backing | warm neutral', (.49, .43, .33), .7, True)
papermat = material('Natural textured paper', (.66, .57, .44), .86, True)
ink = material('Muted terracotta ink', (.48, .32, .21), .9, True)
sunmat = material('Muted sand ink', (.54, .42, .29), .9, True)
groundmat = material('Studio | light warm gray', (.40, .39, .37), .8)

def mesh_obj(name, verts, faces, coll, mat=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v * MM for v in p) for p in verts], [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    coll.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob

def active(ob):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

def bevel(ob, amount, segments=4, apply=False):
    m = ob.modifiers.new('Soft machined edges', 'BEVEL')
    m.width = amount * MM
    m.segments = segments
    if apply:
        active(ob)
        bpy.ops.object.modifier_apply(modifier=m.name)
    return m

def box(name, dims, loc, coll, mat=None, edge=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(v*MM for v in loc))
    ob = move(bpy.context.object, coll)
    ob.name = name
    ob.dimensions = tuple(v*MM for v in dims)
    active(ob)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        ob.data.materials.append(mat)
    if edge:
        bevel(ob, edge)
    return ob

def outline(half, radius):
    pts = []
    for cx, cz, start in [(half-radius, half-radius, 0),
                          (-half+radius, half-radius, 90),
                          (-half+radius, -half+radius, 180),
                          (half-radius, -half+radius, 270)]:
        for i in range(13):
            a = math.radians(start + i*90/12)
            pts.append((cx+radius*math.cos(a), cz+radius*math.sin(a)))
    return pts

# Cross section: front opening 76 mm, rear rebate 80 mm, total 12 mm.
profile = [(50, 2, -6), (38, .8, -6), (38, .8, -3),
           (40, 1, -3), (40, 1, 6), (50, 2, 6)]
verts = [(x,y,z+50) for h,r,y in profile for x,z in outline(h,r)]
n = len(outline(50,2))
faces = []
for j in range(len(profile)):
    for i in range(n):
        a, b = j*n+i, j*n+(i+1)%n
        c, d = ((j+1)%len(profile))*n+(i+1)%n, ((j+1)%len(profile))*n+i
        faces.append((a,b,c,d))
frame = mesh_obj('Frame | 100 x 100 x 12 mm', verts, faces, model, ivory)
bevel(frame, .55, 4, True)

def capsule(name, radius, bottom, top, y0, y1):
    # Capsule outline in XZ, extruded along wall-normal Y.
    points=[]
    for i in range(49):
        a = math.pi*i/48
        points.append((radius*math.cos(a), top+radius*math.sin(a)))
    for i in range(49):
        a = math.pi+math.pi*i/48
        points.append((radius*math.cos(a), bottom+radius*math.sin(a)))
    count=len(points)
    v=[(x,y,z) for y in (y0,y1) for x,z in points]
    f=[tuple(range(count-1,-1,-1)), tuple(range(count,2*count))]
    f += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    return mesh_obj(name,v,f,model)

def cut(ob, cutter):
    active(ob)
    mod=ob.modifiers.new('Recess | '+cutter.name,'BOOLEAN')
    mod.operation='DIFFERENCE'
    mod.solver='EXACT'
    mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)

# Blind internal head channel + rear entry and narrow shank retention opening.
cut(frame,capsule('Internal nail-head travel',3.2,93.5,96.0,.5,4.2))
cut(frame,capsule('Lower nail-head entry',2.7,92.8,92.8,.5,6.8))
cut(frame,capsule('Upper shank slot',1.6,92.8,96.0,4.0,6.8))

back = box('Removable backing | 79.6 x 79.6 x 2 mm', (79.6,2,79.6), (0,4.4,50), model,boardmat,.25)
support = box('Artwork support insert', (79.5,6.2,79.5), (0,.25,50), art,papermat,.15)
# Front paper is tucked under the 2 mm front lip.
paper = box('Art paper | replaceable', (79.4,.1,79.4), (0,-2.93,50), art,papermat)

def ink_shape(name, points, mat):
    return mesh_obj(name,[(x,-2.991,z) for x,z in points],[tuple(range(len(points)))],art,mat)

circle=[(14+3.4*math.cos(i*2*math.pi/96),69+3.4*math.sin(i*2*math.pi/96)) for i in range(96)]
ink_shape('Artwork | small sun',circle,sunmat)
theta=math.radians(12)
arch=[]
for i in range(97):
    a=math.pi*i/96
    x,z=18*math.cos(a),18*math.sin(a)
    arch.append((-4+x*math.cos(theta)-z*math.sin(theta),32+x*math.sin(theta)+z*math.cos(theta)))
ink_shape('Artwork | rising semicircle',arch,ink)

# Three flush retaining tabs, matching the reference. These are concept hardware.
for name,dims,loc in [('Left',(5,.6,7),(-40,5.7,50)),
                      ('Right',(5,.6,7),(40,5.7,50)),
                      ('Bottom',(7,.6,5),(0,5.7,10))]:
    cut(frame,box('Tab recess',tuple(v+.16 for v in dims),loc,model))
    box('Retaining tab | '+name,dims,loc,model,ivory,.18)
bevel(frame,.055,3)
for p in frame.data.polygons:
    p.use_smooth=True
normal=frame.modifiers.new('Weighted face normals','WEIGHTED_NORMAL')
normal.keep_sharp=True
frame['outer_dimensions_mm']=[100,100,12]
frame['front_opening_mm']=[76,76]
frame['border_mm']=12.0
frame['keyhole_entry_diameter_mm']=5.4
frame['keyhole_slot_width_mm']=3.2
frame['head_channel_depth_mm']=3.7
frame['mounting_note']='One nail only. Entry below slot. Nail dimensions are provisional.'

refpath=ROOT/'images/picture-frame-reference.png'
im=bpy.data.images.load(str(refpath),check_existing=True)
im.pack()
ref=bpy.data.objects.new('Original image | packed reference',None)
ref.empty_display_type='IMAGE'
ref.data=im
ref.empty_display_size=.2
refs.objects.link(ref)
ref.hide_render=True
ref.hide_set(True)

floor=box('Studio floor',(2000,2000,1),(0,0,-.8),studio,groundmat)
def aim(ob,target):
    ob.rotation_euler=(Vector(tuple(v*MM for v in target))-ob.location).to_track_quat('-Z','Y').to_euler()

def camera(name,loc,target,scale):
    data=bpy.data.cameras.new(name)
    ob=bpy.data.objects.new(name,data)
    studio.objects.link(ob)
    ob.location=tuple(v*MM for v in loc)
    aim(ob,target)
    data.type='ORTHO'
    data.ortho_scale=scale*MM
    data.clip_start=.0001
    data.clip_end=10
    return ob

hero=camera('Camera | Front three-quarter',(145,-240,150),(0,0,50),145)
rear=camera('Camera | Rear',(0,270,50),(0,0,50),125)
detail=camera('Camera | Keyhole detail',(18,65,111),(0,3,94.5),27)
front=camera('Camera | Front orthographic',(0,-270,50),(0,0,50),125)
def area(name,loc,power,size):
    data=bpy.data.lights.new(name,'AREA')
    ob=bpy.data.objects.new(name,data)
    studio.objects.link(ob)
    ob.location=tuple(v*MM for v in loc)
    data.energy=power
    data.shape='DISK'
    data.size=size*MM
    aim(ob,(0,0,50))

area('Key softbox',(-95,-130,220),4,150)
area('Fill softbox',(140,-70,110),1.3,120)
area('Rear softbox',(-90,140,170),3.5,120)
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.72,.76,.82,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25
scene.render.engine='CYCLES'
scene.cycles.samples=40
scene.cycles.use_denoising=True
scene.render.resolution_x=1100
scene.render.resolution_y=1100
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'
scene.view_settings.exposure=-1.8
scene.camera=hero

# Inspect evaluated solid geometry before delivery.
bpy.context.view_layer.update()
deps=bpy.context.evaluated_depsgraph_get()
ev=frame.evaluated_get(deps)
bm=bmesh.new()
bm.from_mesh(ev.to_mesh())
boundary=sum(not e.is_manifold for e in bm.edges)
volume=abs(bm.calc_volume())/(MM**3)
bm.free()
ev.to_mesh_clear()
assert boundary == 0, f'Frame has {boundary} non-manifold edges'
assert volume>0
assert all(abs(a-b)<.01 for a,b in zip([v/MM for v in frame.dimensions],[100,12,100]))
report={'frame_dimensions_xyz_mm':[round(v/MM,4) for v in frame.dimensions],
        'front_opening_mm':[76,76],'rear_rebate_mm':[80,80],
        'non_manifold_edges':boundary,'frame_volume_mm3':round(volume,2),
        'nail_mounts':1,'entry_diameter_mm':5.4,'slot_width_mm':3.2,
        'physical_fit_tested':False}
(ROOT/'model-checks.json').write_text(json.dumps(report,indent=2))
notes=bpy.data.texts.new('MODEL NOTES')
notes.write('100 x 100 mm frame, 12 mm deep, 76 x 76 mm visible opening.\n'
            'X = horizontal, Y = depth (rear positive), Z = vertical; dimensions in meters, UI in millimeters.\n'
            'The removable back and three flush tabs follow the reference visually.\n'
            'One rear blind keyhole: 5.4 mm entry, 3.2 mm shank slot, 3.7 mm head channel depth.\n'
            'Nail fit, tab fastening and material strength require real hardware verification before fabrication.\n'
            'Reference image packed inside this file. Model / artwork / studio are separate collections.\n')
active(frame)
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type=='VIEW_3D':
            a.spaces.active.clip_start=.0001
            a.spaces.active.clip_end=10
            a.spaces.active.region_3d.view_distance=.20
            a.spaces.active.region_3d.view_location=(0,0,.05)
            a.spaces.active.region_3d.view_rotation=hero.rotation_euler.to_quaternion()
            a.spaces.active.overlay.show_floor=False
            a.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'picture-frame.blend'))
for cam,name in [(hero,'picture-frame-front.png'),(rear,'picture-frame-back.png'),(detail,'picture-frame-keyhole.png')]:
    scene.camera=cam
    floor.hide_render=(cam != hero)
    scene.render.filepath=str(ROOT/'images'/name)
    bpy.ops.render.render(write_still=True)
scene.camera=hero
floor.hide_render=False
scene.render.filepath='//images/picture-frame-front.png'
# Save final camera state without generating a redundant backup.
prefs=bpy.context.preferences.filepaths
prefs.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'picture-frame.blend'))
print(json.dumps(report))

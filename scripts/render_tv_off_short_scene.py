"""Render a premium architectural TV OFF interior still.
The camera is locked. Each UTC slot selects a distinct interior art direction.
"""
import bpy, math, os, sys, argparse, random
from mathutils import Vector

argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]
p=argparse.ArgumentParser()
p.add_argument("--out",required=True); p.add_argument("--kind",required=True)
p.add_argument("--slot",required=True); p.add_argument("--style",default="")
p.add_argument("--screen-image",default="")
a=p.parse_args(argv)
seed=sum(ord(x) for x in a.slot+a.kind+a.style)
rng=random.Random(seed)
scene_id=(int(a.slot[-2:]) + int(a.slot[-4:-2])*3) % 5

bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
for datablocks in (bpy.data.materials,bpy.data.curves,bpy.data.cameras,bpy.data.lights):
    pass

def material(name,color,rough=.5,metal=0, emission=None, strength=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=(*color,1)
    bs.inputs["Roughness"].default_value=rough
    bs.inputs["Metallic"].default_value=metal
    if emission:
        bs.inputs["Emission Color"].default_value=(*emission,1)
        bs.inputs["Emission Strength"].default_value=strength
    return m

def cube(name,loc,scale,mat,bevel=.04):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object; o.name=name; o.dimensions=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mat)
    if bevel:
        b=o.modifiers.new("Soft architectural edges","BEVEL"); b.width=bevel; b.segments=4
        o.modifiers.new("Weighted corner normals","WEIGHTED_NORMAL")
    return o

def area(name,loc,power,color,size,target):
    bpy.ops.object.light_add(type="AREA",location=loc)
    o=bpy.context.object; o.name=name; o.data.energy=power; o.data.color=color
    o.data.shape="DISK"; o.data.size=size
    o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler()

def cylinder(name,loc,radius,depth,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=radius,depth=depth,location=loc)
    o=bpy.context.object; o.name=name; o.data.materials.append(mat)
    b=o.modifiers.new("Rounded edge","BEVEL"); b.width=.025; b.segments=3
    return o

# Art direction: five genuinely different rooms, not a filter applied to one room.
styles=[
 ("MIDNIGHT BLUE",(.025,.055,.12),(.12,.16,.23),(.08,.22,.42),(.7,.78,1.0)),
 ("NEON DREAMS",(.045,.025,.10),(.16,.10,.23),(.34,.10,.72),(.72,.52,1.0)),
 ("COZY EVENING",(.12,.065,.035),(.24,.15,.09),(.78,.34,.10),(1.0,.68,.36)),
 ("CITY NIGHTS",(.018,.035,.065),(.09,.13,.19),(.12,.30,.55),(.50,.72,1.0)),
 ("FOREST RETREAT",(.035,.075,.055),(.12,.17,.12),(.13,.34,.22),(.68,.82,.60)),
]
label,wall_color,sofa_color,accent,light_color=styles[scene_id]
if a.kind=="brown_noise":
    accent=(.62,.32,.12); light_color=(1.0,.62,.32)
elif a.kind=="original_music" and scene_id in (0,1,3):
    accent=(.32,.22,.72); light_color=(.70,.60,1.0)

wall=material("Matte architectural plaster",wall_color,.88)
floor=material("Natural smoked oak floor",(.12,.085,.06),.38)
wood=material("Walnut joinery",(.16,.075,.035),.3)
sofa=material("Premium textured upholstery",sofa_color,.94)
black=material("TV bezel",(.006,.008,.012),.22,.45)
screen=material("TV glass",(.003,.008,.018),.12,.25,(.015,.035,.075),.18)
metal=material("Brushed dark metal",(.16,.18,.21),.28,.8)
glass=material("Night window glass",(.008,.025,.055),.12,.35,accent,.16)
glow=material("Architectural accent light",accent,.25,.15,accent,2.0)
cream=material("Linen cushions",(.58,.52,.43),.96)
rug=material("Woven rug",(.11,.095,.085),.98)

# Enclosed architectural shell and floor.
cube("Oak floor",(0,0,-.12),(10,12,.24),floor,.02)
cube("Rear feature wall",(0,4.8,2.8),(10,.22,5.6),wall,.02)
cube("Left return wall",(-5,0,2.8),(.22,9.6,5.6),wall,.02)
cube("Right return wall",(5,0,2.8),(.22,9.6,5.6),wall,.02)
cube("Ceiling",(0,0,5.6),(10,9.6,.16),wall,.02)

# Large window composition changes by room type.
if scene_id in (0,3,4):
    wx=-2.65 if scene_id!=3 else 2.55
    cube("Panoramic window",(wx,4.66,2.95),(3.65,.035,3.95),glass,.015)
    for dx in [-1.8,0,1.8]:
        cube("Slim black window mullion",(wx+dx,4.59,2.95),(.045,.09,4.0),metal,.01)
    cube("Window sill",(wx,4.48,.98),(3.8,.32,.12),wood,.025)
    if scene_id==4:
        # Forest silhouette beyond the glass.
        for i in range(11):
            x=wx-1.65+i*.33
            h= rng.uniform(1.2,3.0)
            bpy.ops.mesh.primitive_cone_add(vertices=12,radius1=.38,radius2=0,depth=h,location=(x,4.9,1.0+h/2))
            bpy.context.object.data.materials.append(material("Pine silhouette "+str(i),(.018,.07,.035),.95))
else:
    cube("Arched feature window",(0,4.66,3.0),(3.3,.035,4.0),glass,.02)
    for x in [-1.65,0,1.65]:
        cube("Window frame",(x,4.58,3.0),(.055,.09,4.05),metal,.01)

# TV wall and screen are the visual anchor in every room.
cube("Floating walnut media wall",(0,4.48,2.25),(4.6,.18,2.8),wood,.08)
cube("Large flat screen television",(0,4.30,2.45),(3.65,.12,2.12),black,.06)
cube("Dark television display",(0,4.225,2.45),(3.48,.018,1.95),screen,.025)
if a.screen_image:
    screen_path=os.path.abspath(a.screen_image)
    if not os.path.isfile(screen_path):
        raise FileNotFoundError("SDXL screen artwork does not exist: "+screen_path)
    image=bpy.data.images.load(screen_path,check_existing=False)
    image.pack()
    display_mat=bpy.data.materials.new("SDXL artwork displayed on TV")
    display_mat.use_nodes=True
    nodes=display_mat.node_tree.nodes
    links=display_mat.node_tree.links
    bsdf=nodes.get("Principled BSDF")
    tex=nodes.new("ShaderNodeTexImage")
    tex.image=image
    tex.interpolation="Linear"
    links.new(tex.outputs["Color"],bsdf.inputs["Base Color"])
    emission_color=bsdf.inputs.get("Emission Color")
    if emission_color is not None:
        links.new(tex.outputs["Color"],emission_color)
        strength=bsdf.inputs.get("Emission Strength")
        if strength is not None:
            strength.default_value=0.18
    bsdf.inputs["Roughness"].default_value=0.22
    bpy.ops.mesh.primitive_plane_add(size=2,location=(0,4.205,2.45),rotation=(math.radians(90),0,0))
    display=bpy.context.object
    display.name="SDXL artwork on television screen"
    display.scale=(1.735,0.97,1)
    display.data.materials.append(display_mat)
    print("TV_OFF_SDXL_SCREEN_IMAGE",screen_path)
cube("Floating media console",(0,4.05,.72),(4.9,.65,.38),wood,.06)
for x in [-1.8,1.8]:
    cube("Console shadow gap",(x,3.70,.70),(.025,.02,.22),metal,.005)

# Distinct living-room furniture, grounded proportions and layered textiles.
cube("Large sectional sofa",(0,-1.05,.72),(4.45,1.35,.85),sofa,.24)
cube("Sectional back",(0,-.28,1.22),(4.35,.42,1.18),sofa,.2)
for x in [-1.45,-.55,.55,1.45]:
    pillow= cube("Linen sofa cushion",(x,-.04,1.55),(.72,.24,.66),cream,.15)
    pillow.rotation_euler[1]=rng.uniform(-.08,.08)
cube("Layered area rug",(0,-1.35,.015),(6.0,3.5,.035),rug,.015)
cube("Low coffee table",(0,-2.55,.42),(2.5,1.05,.14),wood,.07)
for x in [-.92,.92]:
    cube("Coffee table leg",(x,-2.55,.22),(.08,.08,.38),metal,.02)

# Scene-specific architectural signature: fireplace, neon coves, skyline, or biophilic details.
if scene_id==2:
    cube("Stone fireplace surround",(-3.65,3.9,1.35),(1.65,.58,2.55),material("Warm limestone",(.42,.31,.22),.82),.08)
    cube("Firebox recess",(-3.65,3.58,1.15),(1.22,.035,1.05),black,.02)
    fire=material("Fire glow",(1.0,.22,.025),.25,0,(1.0,.12,.015),4.0)
    for i in range(9):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=12,radius=1,location=(-4.12+i*.12,3.53,.88+(i%3)*.12))
        o=bpy.context.object; o.name="Fireplace ember form"; o.scale=(.055,.045,.18+(i%2)*.06); o.data.materials.append(fire)
elif scene_id==1:
    for z in [1.0,1.35,1.7,2.05,2.4,2.75,3.1,3.45,3.8]:
        cube("Purple recessed LED reveal",(0,4.34,z),(4.1,.025,.018),glow,.005)
elif scene_id==3:
    # Distant city lights visible through the glass.
    for i in range(36):
        x=2.55+rng.uniform(-1.65,1.65); z=rng.uniform(1.25,4.55)
        dot=material("Distant skyline light "+str(i),(.5,.62,.9),.25,0,(.35,.52,1.0),1.4)
        cube("Distant skyline light",(x,4.88,z),(.035,.018,.035),dot,.005)
elif scene_id==4:
    for x in [-3.8,3.8]:
        cylinder("Indoor planter",(x,1.3,.42),.38,.78,material("Stone planter",(.22,.24,.19),.75))
        for i in range(7):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=12,radius=1,location=(x+rng.uniform(-.3,.3),1.3+rng.uniform(-.3,.3),1.0+rng.uniform(.2,.8)))
            o=bpy.context.object; o.name="Broad-leaf indoor plant"; o.scale=(.16,.09,.32); o.data.materials.append(material("Deep green foliage",(.025,.16,.07),.9))

# Minimal practical lighting, no floating rings, no decorative HUD, no random clutter.
area("Soft warm ceiling bounce",(0,1.0,5.0),1050,(1.0,.78,.58),5,(0,0,0))
area("Cool window fill",(-3.5,3.2,3.8),850,light_color,3,(0,0,1))
area("Soft sofa key",(0,-4.0,3.8),520,(.72,.80,1.0),4,(0,1,1))
area("TV wall accent",(3.6,3.5,3.0),260,light_color,2,(0,2,1))

# One immutable camera transform for the entire 30-second video.
bpy.ops.object.camera_add(location=(0,-9.6,2.55))
cam=bpy.context.object
cam.rotation_euler=(Vector((0,1.55,2.05))-cam.location).to_track_quat("-Z","Y").to_euler()
cam.data.lens=42; cam.data.sensor_width=36; cam.data.sensor_fit="VERTICAL"
scene=bpy.context.scene; scene.camera=cam
scene.render.engine="BLENDER_EEVEE_NEXT"; scene.eevee.taa_render_samples=96
scene.render.resolution_x=1080; scene.render.resolution_y=1920; scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"; scene.render.image_settings.color_mode="RGBA"
scene.render.film_transparent=False
scene.view_settings.view_transform="AgX"; scene.view_settings.look="AgX - Medium High Contrast"
scene.world.color=(.012,.016,.026)
scene.camera.data.dof.use_dof=True; scene.camera.data.dof.focus_distance=11; scene.camera.data.dof.aperture_fstop=8.0
scene.render.filepath=a.out
bpy.ops.render.render(write_still=True)
print("TV_OFF_PREMIUM_INTERIOR_RENDERED",a.out,"scene_id",scene_id,"room",label,"kind",a.kind)

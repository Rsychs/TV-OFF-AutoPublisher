"""Create one distinct cinematic 3D TV OFF scene for a vertical Short.
Run with: blender --background --python scripts/render_tv_off_short_scene.py -- --out FILE --kind white_noise --slot YYYYMMDDHH
"""
import bpy, math, os, sys, argparse
from mathutils import Vector

argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]
ap=argparse.ArgumentParser()
ap.add_argument("--out",required=True); ap.add_argument("--kind",required=True); ap.add_argument("--slot",required=True)
a=ap.parse_args(argv)
kind=a.kind; seed=int(a.slot[-2:]) + int(a.slot[-4:-2])*3
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
for datablocks in (bpy.data.materials,bpy.data.curves,bpy.data.cameras,bpy.data.lights):
    pass

palettes={
 "white_noise": ((.48,.70,1.0),(.035,.075,.15),(.72,.82,.95)),
 "brown_noise": ((1.0,.48,.17),(.12,.055,.025),(.82,.58,.34)),
 "original_music": ((.63,.42,1.0),(.055,.035,.13),(.92,.68,.42)),
}
accent,deep,light=palettes[kind]
def mat(name,color,rough=.55,metal=0,emission=None,strength=0):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
 p=m.node_tree.nodes.get("Principled BSDF"); p.inputs["Base Color"].default_value=(*color,1); p.inputs["Roughness"].default_value=rough; p.inputs["Metallic"].default_value=metal
 if emission:
  p.inputs["Emission Color"].default_value=(*emission,1); p.inputs["Emission Strength"].default_value=strength
 return m
def cube(name,loc,scale,ma,bev=.04):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev:
  b=o.modifiers.new("Soft rounded craftsmanship","BEVEL"); b.width=bev; b.segments=4; o.modifiers.new("Weighted normals","WEIGHTED_NORMAL")
 return o
def sphere(name,loc,scale,ma):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,radius=1,location=loc); o=bpy.context.object; o.name=name; o.scale=scale; o.data.materials.append(ma); bpy.ops.object.shade_smooth(); return o
def cyl(name,loc,r,depth,ma):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=name; o.data.materials.append(ma); b=o.modifiers.new("Rounded edge","BEVEL"); b.width=.025; b.segments=3; return o
def light_obj(name,loc,power,color,size,target):
 bpy.ops.object.light_add(type="AREA",location=loc); o=bpy.context.object; o.name=name; o.data.energy=power; o.data.color=color; o.data.shape="DISK"; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler()
def text_obj(body,loc,size,ma):
 cu=bpy.data.curves.new("TV OFF brand lettering","FONT"); cu.body=body; cu.size=size; cu.extrude=.002; ob=bpy.data.objects.new(body,cu); bpy.context.collection.objects.link(ob); ob.location=loc; ob.data.materials.append(ma); return ob

wall=mat("Deep architectural walls",deep,.9); floor=mat("Warm natural flooring",(.18,.13,.095),.42)
wood=mat("Walnut and oak",(.20,.095,.045),.32); fabric=mat("Soft premium upholstery",(.55,.48,.38),.95)
darkfabric=mat("Midnight velvet",(.045,.06,.09),.98); metal=mat("Brushed metal",(.38,.28,.18),.25,.78)
glass=mat("Night glass",(.012,.035,.075),.12,.25,accent,.45)
glow=mat("Luminous accent",accent,.22,.15,accent,3.0); ceramic=mat("Matte ceramic",(.28,.25,.22),.25)
green=mat("Indoor foliage",(.025,.13,.07),.8)

# Five genuinely different modeled spaces, rotated deterministically by publishing slot.
scene_id=seed%5
cube("Continuous floor",(0,0,-.12),(9,11,.24),floor,.02)
cube("Rear wall",(0,4.5,2.7),(9,.18,5.4),wall,.02)
cube("Left wall",(-4.5,0,2.7),(.18,9,5.4),wall,.02)
cube("Ceiling",(0,0,5.4),(9,9,.12),wall,.02)

if scene_id==0: # cinematic lounge with fireplace and window
 cube("Panoramic night window",(2.3,4.38,2.8),(3.5,.04,3.8),glass,.02)
 for x in [.55,2.3,4.05]: cube("Window mullion",(x,4.32,2.8),(.045,.1,3.85),metal,.01)
 cube("Stone fireplace surround",(-2.7,3.95,1.45),(2.2,.55,2.8),wood,.08)
 cube("Fireplace dark opening",(-2.7,3.64,1.25),(1.55,.05,1.05),darkfabric,.02)
 for i in range(8): sphere("Firelight",(-3.35+i*.18,3.55,1.0+(i%3)*.13),(.07,.04,.18),glow)
 cube("Lounge sofa",(0,-.6,.65),(4.3,1.3,1.1),fabric,.22)
 cube("Sofa back",(0,.05,1.25),(4.2,.38,1.5),darkfabric,.2)
 cube("Stone coffee table",(0,-2,.45),(2.5,1.1,.15),metal,.08)
elif scene_id==1: # calm bedroom, layered bedding and arched window
 cube("Tall arched window",(0,4.36,3.0),(3.0,.04,3.9),glass,.02)
 bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,radius=1,location=(0,4.35,4.55)); arch=bpy.context.object; arch.scale=(1.5,.035,.8); arch.data.materials.append(glass)
 cube("Low upholstered bed",(0,-.25,.65),(4.4,3.1,.65),darkfabric,.18)
 cube("Tall padded headboard",(0,1.25,1.35),(4.5,.25,1.5),fabric,.15)
 for x in [-1.25,1.25]: cube("Plump linen pillow",(x,.55,1.15),(1.4,.75,.3),fabric,.16)
 cube("Folded knit blanket",(0,-1.05,1.02),(4.1,1.1,.12),wood,.12)
 for x in [-2.7,2.7]: cyl("Bedside table",(x,.65,.48),.48,.85,wood)
elif scene_id==2: # design studio with desk, shelving and task light
 cube("Desk top",(0,1.2,1.35),(5.3,1.25,.16),wood,.07)
 for x in [-2.2,2.2]: cube("Desk leg",(x,1.2,.68),(.12,.12,1.3),metal,.025)
 for z in [2.2,3.1,4.0]:
  cube("Floating wall shelf",(0,4.25,z),(5.2,.35,.12),wood,.035)
  for i in range(5):
   x=-2.0+i*.9
   cube("Design book",(x,4.0,z+.23),(.22,.22,.36+(i%2)*.1),fabric if i%2 else metal,.015)
 cube("Studio chair seat",(0,-.25,.8),(1.4,1.2,.25),darkfabric,.14)
 cube("Studio chair back",(0,.25,1.45),(1.35,.22,1.1),fabric,.14)
 cyl("Task lamp base",(1.65,.9,1.5),.22,.08,metal)
 cube("Task lamp arm",(1.65,.9,2.0),(.07,.07,1.0),metal,.025)
 sphere("Task lamp shade",(1.65,.9,2.55),(.32,.32,.18),glow)
elif scene_id==3: # reading nook with window, lounge chair and bookcase
 cube("Tall moonlit window",(-2.6,4.35,2.8),(2.3,.04,4.0),glass,.02)
 for x in [-3.75,-2.6,-1.45]: cube("Window frame",(x,4.28,2.8),(.05,.12,4.1),metal,.01)
 cube("Bookcase",(2.6,3.95,2.35),(2.0,.55,4.5),wood,.04)
 for z in [.7,1.65,2.6,3.55]:
  cube("Bookshelf shelf",(2.6,3.62,z),(1.9,.12,.09),metal,.015)
  for i in range(5): cube("Book spine",(1.9+i*.3,3.5,z+.22),(.19,.16,.35+(i%3)*.12),fabric if i%2 else darkfabric,.012)
 cube("Reading chair",(0,-.3,.8),(2.0,1.8,1.1),fabric,.24)
 cube("Reading chair back",(0,.45,1.55),(1.95,.35,1.5),darkfabric,.2)
 cyl("Round side table",(-1.55,-.2,.55),.42,.12,wood)
elif scene_id==4: # music room with grand piano silhouette
 cube("Acoustic feature wall",(0,4.3,2.6),(8.7,.12,5.0),darkfabric,.025)
 # grand piano body, lid, keyboard, legs
 bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,radius=1,location=(0,.4,1.0)); piano=bpy.context.object; piano.name="Grand piano body"; piano.scale=(2.0,1.35,.48); piano.data.materials.append(black:=mat("Piano lacquer",(.012,.016,.025),.16,.72))
 cube("Piano keyboard",(0,-.85,1.12),(2.35,.22,.12),fabric,.02)
 for i in range(25): cube("Piano key",( -1.1+i*.092,-.98,1.19),(.075,.05,.035),metal if i%7 in [1,3,6] else fabric,.004)
 lid=cube("Grand piano raised lid",(.65,.35,1.65),(2.7,1.7,.08),black,.035); lid.rotation_euler[1]=-.12
 cyl("Piano stool",(0,-2,.55),.5,.18,wood)
 cube("Piano stool stem",(0,-2,.28),(.12,.12,.45),metal,.02)

# Shared crafted accents: sculptural lamp, plant, floating luminous rings and brand plaque.
cyl("Sculptural lamp stem",(3.45,-.1,1.45),.045,2.7,metal)
sphere("Sculptural lamp globe",(3.45,-.1,2.85),(.32,.32,.38),glow)
cyl("Planter",( -3.4,1.7,.38),.34,.7,ceramic)
cyl("Plant trunk",(-3.4,1.7,1.35),.045,1.4,wood)
for i in range(14):
 ang=i*2.399; sphere("Distinct leaf cluster",(-3.4+math.cos(ang)*(.25+(i%3)*.09),1.7+math.sin(ang)*(.25+(i%3)*.09),1.45+(i%5)*.24),(.14,.09,.24),green)
# floating light sculpture - distinctive signature in each room
for i in range(3):
 bpy.ops.mesh.primitive_torus_add(major_radius=1.0+i*.23,minor_radius=.018,major_segments=96,minor_segments=8,location=(0,2.5,3.8-i*.24),rotation=(math.radians(65),0,math.radians(i*25+seed*9)))
 o=bpy.context.object; o.name="TV OFF luminous sound ring"; o.data.materials.append(glow)

# Category-dependent lighting and accent
area_color=(accent[0],accent[1],accent[2])
light_obj("Large soft key",(0,-3.5,5.0),1250,(1,.78,.62),5,(0,1,1))
light_obj("Category rim",(3.6,3.0,4.2),950,area_color,3,(0,0,1))
light_obj("Cool fill",(-3,-1,3.0),450,(.45,.58,1),4,(0,1,1))
light_obj("Warm practical",(3.2,0,2.8),300,(1,.52,.24),1.5,(0,0,0))
# Camera portrait composition with a subtle animated orbit/zoom baked into the final FFmpeg motion pass.
bpy.ops.object.camera_add(location=(0,-8.7,3.0)); cam=bpy.context.object
cam.rotation_euler=(Vector((0,1.0,2.15))-cam.location).to_track_quat("-Z","Y").to_euler()
cam.data.lens=34; cam.data.sensor_width=36; cam.data.sensor_fit="VERTICAL"; bpy.context.scene.camera=cam
scene=bpy.context.scene
scene.render.engine="BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples=64
scene.render.resolution_x=720; scene.render.resolution_y=1280; scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"; scene.render.image_settings.color_mode="RGBA"
scene.render.film_transparent=False; scene.view_settings.view_transform="AgX"; scene.view_settings.look="AgX - Medium High Contrast"
scene.world.color=(.018,.025,.045)
scene.use_nodes=True; nt=scene.node_tree; nt.nodes.clear()
rl=nt.nodes.new("CompositorNodeRLayers"); glare=nt.nodes.new("CompositorNodeGlare"); glare.glare_type="FOG_GLOW"; glare.threshold=1.0; glare.quality="HIGH"
comp=nt.nodes.new("CompositorNodeComposite"); nt.links.new(rl.outputs["Image"],glare.inputs["Image"]); nt.links.new(glare.outputs["Image"],comp.inputs["Image"])
scene.camera.data.dof.use_dof=True; scene.camera.data.dof.focus_distance=10; scene.camera.data.dof.aperture_fstop=5.6
scene.render.filepath=a.out
bpy.ops.render.render(write_still=True)
print("TV_OFF_3D_SCENE_RENDERED",a.out,"scene_id",scene_id,"category",kind)

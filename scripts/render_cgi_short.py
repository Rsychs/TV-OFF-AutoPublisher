import bpy, math, os
from mathutils import Vector
OUT=os.environ.get("TV_OFF_RENDER_DIR","/tmp/tv-off-cgi"); os.makedirs(OUT,exist_ok=True)
QUALITY=os.environ.get("QUALITY","preview").lower()
PREVIEW=QUALITY!="production"
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)

def mat(name,color,rough=.5,metal=0,noise=0,bump=.08):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
 n=m.node_tree.nodes; p=n.get("Principled BSDF"); p.inputs["Base Color"].default_value=(*color,1); p.inputs["Roughness"].default_value=rough; p.inputs["Metallic"].default_value=metal
 if noise:
  tex=n.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value=noise; tex.inputs["Detail"].default_value=3
  ramp=n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].position=.2; ramp.color_ramp.elements[0].color=(*[v*.72 for v in color],1); ramp.color_ramp.elements[1].position=.8; ramp.color_ramp.elements[1].color=(*[min(1,v*1.18) for v in color],1)
  bumpn=n.new("ShaderNodeBump"); bumpn.inputs["Strength"].default_value=bump; bumpn.inputs["Distance"].default_value=.035
  m.node_tree.links.new(tex.outputs["Fac"],ramp.inputs["Fac"]); m.node_tree.links.new(ramp.outputs["Color"],p.inputs["Base Color"]); m.node_tree.links.new(tex.outputs["Fac"],bumpn.inputs["Height"]); m.node_tree.links.new(bumpn.outputs["Normal"],p.inputs["Normal"])
 return m
def cube(name,loc,scale,ma,bevel=.04):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel:
  b=o.modifiers.new("Soft crafted edges","BEVEL"); b.width=bevel; b.segments=4
  o.modifiers.new("Weighted corner normals","WEIGHTED_NORMAL")
 return o
def cyl(name,loc,r,depth,ma,verts=48):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=name; o.data.materials.append(ma); b=o.modifiers.new("Edge highlights","BEVEL"); b.width=.025; b.segments=3; o.modifiers.new("Weighted normals","WEIGHTED_NORMAL"); return o
def sphere(name,loc,scale,ma):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,radius=1,location=loc); o=bpy.context.object; o.name=name; o.scale=scale; o.data.materials.append(ma); bpy.ops.object.shade_smooth(); return o
def aim(o,p): o.rotation_euler=(Vector(p)-o.location).to_track_quat("-Z","Y").to_euler()
def area(name,loc,power,color,size,target):
 bpy.ops.object.light_add(type="AREA",location=loc); o=bpy.context.object; o.name=name; o.data.energy=power; o.data.color=color; o.data.shape="DISK"; o.data.size=size; aim(o,target)
# materials with subtle surface variation
walnut=mat("Natural smoked walnut",(.16,.075,.038),.28,0,5,.12)
floor=mat("Oiled oak floor",(.27,.16,.085),.32,0,3,.08)
stone=mat("Honed dark travertine",(.20,.19,.17),.32,0,18,.12)
plaster=mat("Limewash plaster",(.57,.49,.39),.88,0,22,.12)
linen=mat("Ivory woven linen",(.72,.66,.55),.92,0,95,.18)
boucle=mat("Charcoal boucle",(.12,.13,.13),.95,0,130,.2)
brass=mat("Satin brushed brass",(.55,.34,.13),.24,.78,40,.04)
black=mat("Blackened steel",(.025,.03,.035),.3,.7)
rug=mat("Handwoven wool rug",(.30,.25,.19),1,0,75,.22)
glass=mat("Smoked architectural glass",(.025,.055,.085),.12,.45)
green=mat("Olive foliage",(.07,.16,.075),.8,0,30,.12)
ceramic=mat("Matte ceramic",(.28,.24,.19),.28,0,45,.08)
# shell and oak plank floor
cube("Continuous oak floor",(0,0,-.14),(10,12,.28),floor,.02)
cube("Left limewash wall",(-5,0,2.7),(.18,12,5.4),plaster,.02)
cube("Right limewash wall",(5,0,2.7),(.18,12,5.4),plaster,.02)
cube("Ceiling",(0,0,5.45),(10,12,.16),walnut,.02)
# window wall at far end with tall glazing
cube("Panoramic night glazing",(0,5.92,2.65),(9.7,.07,5.05),glass,.01)
for x in [-4.7,-2.35,0,2.35,4.7]:
 cube("Slim black window mullion",(x,5.84,2.65),(.055,.14,5.1),black,.012)
cube("Window transom",(0,5.82,4.95),(9.7,.12,.06),black,.01)
# subtle city lights beyond glass
for i in range(25):
 x=-4.5+(i%13)*.75; z=.5+(i%5)*.36
 sphere("Distant city light",(x,6.25,z),(.025,.018,.025),brass)
# ceiling cove and wall panels
cube("Walnut feature wall",(0,5.55,2.65),(9.6,.16,5.1),walnut,.025)
for x in [-4.35,-3.25,-2.15,-1.05,.05,1.15,2.25,3.35,4.45]:
 cube("Wall panel reveal",(x,5.44,2.65),(.018,.025,4.75),brass,.005)
cube("Cove LED",(0,4.9,5.18),(8.8,.035,.035),brass,.01)
# fireplace and stone slab
cube("Fireplace stone monolith",(-4.72,1.8,1.65),(.42,3.3,3.3),stone,.07)
cube("Fireplace dark recess",(-4.48,1.8,.85),(.035,2.35,.9),black,.02)
for i in range(9):
 sphere("Natural flame core",(-4.43, .82+i*.24, .92),(.035,.075,.22),mat("Flame amber "+str(i),(1,.18+.025*i,.025),.25,0))
# area rug with layered border
cube("Large wool rug",(0,-.25,.025),(6.7,4.8,.06),rug,.08)
cube("Rug inset border",(0,-.25,.061),(6.25,4.35,.012),linen,.015)
# sofa: plinth, upholstered base, back and arms
cube("Sofa walnut recessed plinth",(0,1.55,.34),(4.7,1.55,.32),walnut,.10)
cube("Sofa upholstered base",(0,1.35,.62),(4.75,1.62,.48),linen,.18)
cube("Sofa back upholstery",(0,2.02,1.24),(4.7,.42,1.18),boucle,.18)
for x in [-2.18,2.18]: cube("Sofa padded arm",(x,1.38,.91),(.42,1.48,.82),linen,.16)
for i,x in enumerate([-1.55,-.52,.52,1.55]):
 cube("Separate tailored back cushion "+str(i),(x,1.78,1.42),(.91,.28,.78),linen if i%2==0 else boucle,.17)
 cube("Seat cushion seam detail "+str(i),(x,1.18,.87),(.82,1.12,.035),linen,.018)
# two sculptural lounge chairs
for x,rot in [(3.35,-.15),(-3.15,.18)]:
 seat=cube("Sculpted lounge chair seat",(x,-1.45,.72),(1.55,1.5,.38),boucle,.18); seat.rotation_euler[2]=rot
 back=cube("Sculpted lounge chair back",(x,-.82,1.35),(1.52,.36,1.25),linen,.2); back.rotation_euler[2]=rot
 for dx in [-.55,.55]:
  leg=cyl("Chair brass foot",(x+dx,-1.45,.31),.035,.58,brass,24)
# coffee table with stone top and metal frame
for x in [-1.15,1.15]:
 for y in [-1.7,-.45]: cyl("Coffee table brass support",(x,y,.34),.035,.58,brass,24)
cube("Floating honed stone coffee table",(0,-1.08,.66),(2.8,1.65,.16),stone,.07)
# books, ceramic vessel and sculptural branches
for i in range(3): cube("Design book "+str(i),(-.78+i*.12,-1.05,.78+i*.065),(.72,.48,.07),[walnut,linen,black][i],.015)
cyl("Sculptural ceramic vase",(.78,-1.05,.98),.18,.48,ceramic)
for i in range(5):
 leaf=sphere("Vase dried branch",(.78+math.sin(i*1.3)*.16,-1.05,1.3+i*.1),(.018,.018,.38),walnut); leaf.rotation_euler[1]=-.25+i*.12
# side tables and decorative lamps
for x,y in [(2.85,1.65),(-2.9,1.65)]:
 cyl("Round walnut side table top",(x,y,.78),.43,.12,walnut)
 cyl("Side table pedestal",(x,y,.42),.10,.62,brass,32)
 cyl("Lamp brass base",(x,y,.91),.16,.08,brass)
 bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.28,radius2=.16,depth=.42,location=(x,y,1.16)); bpy.context.object.data.materials.append(linen)
# indoor olive tree, ceramic planter, many leaves
cyl("Olive tree planter",(4.05,2.7,.42),.42,.8,ceramic)
cyl("Olive tree trunk",(4.05,2.7,1.55),.065,1.7,walnut,24)
for i in range(24):
 a=i*2.399; z=1.7+(i%6)*.35
 branch=sphere("Olive leaf cluster",(4.05+math.cos(a)*(.35+(i%3)*.1),2.7+math.sin(a)*(.35+(i%3)*.1),z),(.16,.09,.27),green); branch.rotation_euler[1]=math.cos(a)*.5
# layered lighting
area("Large warm ceiling bounce",(0,0.2,5.05),1250,(1,.78,.58),5,(0,0,0))
area("Cool window daylight",(0,5.1,4.0),1800,(.52,.68,1),4,(0,0,1))
area("Soft frontal fill",(0,-4.5,3.5),700,(1,.84,.68),5,(0,1,1))
area("Fireplace warm bounce",(-4.1,1.6,1.6),240,(1,.28,.09),1.5,(0,0,1))
area("Accent wall wash",(0,4.8,4.8),500,(1,.62,.34),3,(0,2,2))
# camera: wide establishing view, not a cropped furniture close-up
bpy.ops.object.camera_add(location=(0,-5.0,2.55)); cam=bpy.context.object; cam.data.lens=18; aim(cam,(0,1.35,1.65)); bpy.context.scene.camera=cam
cam.keyframe_insert(data_path="location",frame=1); cam.keyframe_insert(data_path="rotation_euler",frame=1)
cam.location=(.32,-3.65,2.35); aim(cam,(0,1.45,1.55)); cam.keyframe_insert(data_path="location",frame=721); cam.keyframe_insert(data_path="rotation_euler",frame=721)
if cam.animation_data:
 for fc in cam.animation_data.action.fcurves:
  for k in fc.keyframe_points: k.interpolation="BEZIER"
scene=bpy.context.scene
# Cycles is the production renderer; CPU-only so no paid GPU service is required.
scene.render.engine="CYCLES"; scene.cycles.device="CPU"
scene.cycles.samples=24 if PREVIEW else 64
scene.cycles.use_denoising=False  # Ubuntu Blender package is built without OpenImageDenoiser
scene.render.resolution_x=720; scene.render.resolution_y=1280; scene.render.resolution_percentage=100
scene.render.fps=24; scene.frame_start=1; scene.frame_end=1 if PREVIEW else 720
scene.render.image_settings.file_format="PNG"; scene.render.filepath=os.path.join(OUT,"frame_")
scene.view_settings.view_transform="AgX"
scene.world.color=(.025,.03,.045)
scene.camera.data.dof.use_dof=False
scene.render.image_settings.color_mode="RGBA"
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,"tv_off_luxury_lounge.blend"))
if PREVIEW:
 scene.render.filepath=os.path.join(OUT,"TV_OFF_CGI_Preview.png")
 bpy.ops.render.render(write_still=True)
else:
 bpy.ops.render.render(animation=True)

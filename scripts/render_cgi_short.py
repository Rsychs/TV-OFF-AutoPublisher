import bpy, math, os
from mathutils import Vector
out=os.environ.get("TV_OFF_RENDER_DIR","/tmp/tv-off-cgi"); os.makedirs(out,exist_ok=True)
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
def material(n,c,r=.5,metal=0,emit=None,power=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes["Principled BSDF"]; p.inputs["Base Color"].default_value=(*c,1); p.inputs["Roughness"].default_value=r; p.inputs["Metallic"].default_value=metal
 if emit: p.inputs["Emission Color"].default_value=(*emit,1); p.inputs["Emission Strength"].default_value=power
 return m
def box(n,loc,size,ma,bev=.03):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=size; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: b=o.modifiers.new("Rounded edges","BEVEL"); b.width=bev; b.segments=3; o.modifiers.new("Weighted normals","WEIGHTED_NORMAL")
 return o
def light(n,loc,power,color,size,target):
 bpy.ops.object.light_add(type="AREA",location=loc); o=bpy.context.object; o.name=n; o.data.energy=power; o.data.color=color; o.data.shape="DISK"; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler(); return o
def aim(o,t): o.rotation_euler=(Vector(t)-o.location).to_track_quat("-Z","Y").to_euler()
walnut=material("Smoked walnut",(.11,.055,.03),.27); floor=material("Oiled walnut",(.20,.11,.06),.25); stone=material("Graphite marble",(.065,.075,.085),.22); plaster=material("Warm plaster",(.38,.32,.26),.8); linen=material("Ivory linen",(.68,.61,.5),.9); charcoal=material("Boucle charcoal",(.09,.10,.11),.95); brass=material("Brushed brass",(.48,.29,.11),.24,.8); glow=material("Warm LED",(.8,.3,.07),.25,0,(1,.22,.04),3); fire=material("Fire",(.9,.08,.01),.2,0,(1,.08,.005),8); rug=material("Woven rug",(.28,.23,.17),1); glass=material("Night glass",(.01,.03,.07),.2,.35)
box("Floor",(0,0,-.12),(10,12,.24),floor); box("Back wall",(0,5,2.7),(10,.2,5.4),plaster); box("Left stone wall",(-4.9,0,2.7),(.2,10,5.4),stone); box("Ceiling",(0,0,5.45),(10,12,.15),walnut)
box("Panoramic night view",(0,-5.9,2.5),(9.7,.04,5),glass,0)
for x in [-4.7,-2.35,0,2.35,4.7]: box("Black window mullion",(x,-5.8,2.5),(.045,.12,5),walnut,.01)
for i in range(17):
 x=-4.5+i*.55; h=.6+abs(math.sin(i*1.7))*1.6; box("Distant skyline",(x,-6.25,h/2),(.35,.2,h),stone,.01)
mount=material("Distant mountain",(.015,.04,.075),.9)
for i in range(8):
 bpy.ops.mesh.primitive_cone_add(vertices=5,radius1=1.15,radius2=0,depth=1.6,location=(-4.8+i*1.35,-6.35,1.8)); bpy.context.object.data.materials.append(mount)
box("Ceiling cove",(0,4.55,5.17),(8.8,.04,.04),glow,.01)
# fireplace architectural feature
box("Fireplace surround",(-4.62,1.6,1.6),(.38,4,3.2),stone,.07); box("Firebox",(-4.40,1.6,.78),(.05,2.7,.8),charcoal,.01); box("Flame bed",(-4.35,1.6,.52),(.04,2.5,.08),fire,.01)
for i in range(10):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=1,location=(-4.30,.5+i*.24,.67+.06*math.sin(i*2))); o=bpy.context.object; o.scale=(.035,.08,.17); o.data.materials.append(fire)
box("Rug",(0,-.3,.01),(6.5,4.2,.04),rug,.04)
# detailed sectional sofa
box("Sofa plinth",(0,1.2,.38),(4.8,1.4,.45),walnut,.12); box("Sofa seat",(0,.8,.68),(4.65,1.35,.42),linen,.16); box("Sofa back",(0,1.72,1.25),(4.65,.4,1.25),charcoal,.16)
for x in [-1.6,-.55,.55,1.6]: box("Linen cushion",(x,1.43,1.2),(.78,.26,.7),linen,.14)
# lounge chair
box("Lounge chair seat",(3.25,-2,.7),(1.5,1.45,.4),charcoal,.15); box("Lounge chair back",(3.25,-1.42,1.3),(1.45,.35,1.25),linen,.14)
# coffee table and books
for x in [-1.2,1.2]:
 for y in [-1.65,-.45]: box("Brass table leg",(x,y,.3),(.05,.05,.58),brass,.01)
box("Marble coffee table",(0,-1.05,.61),(2.7,1.5,.15),stone,.05)
for i in range(3): box("Art book",(-.7+i*.1,-1.05,.72+i*.055),(.8,.48,.06),[walnut,linen,charcoal][i],.01)
# plant with 3D leaves
pot=material("Ceramic pot",(.13,.10,.07),.3); leaves=material("Olive leaves",(.035,.12,.06),.85)
bpy.ops.mesh.primitive_cone_add(vertices=40,radius1=.32,radius2=.25,depth=.6,location=(4,1.5,.3)); bpy.context.object.data.materials.append(pot)
for i in range(14):
 a=i*2.4; bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=1,location=(4+math.cos(a)*.28,1.5+math.sin(a)*.28,1+(i%5)*.2)); o=bpy.context.object; o.scale=(.12,.055,.34); o.data.materials.append(leaves)
# side table and lamp
box("Side table",(2.8,1.5,.45),(.7,.7,.85),walnut,.06); box("Lamp base",(2.8,1.5,.91),(.25,.25,.07),brass,.02)
bpy.ops.mesh.primitive_cone_add(vertices=40,radius1=.26,radius2=.13,depth=.45,location=(2.8,1.5,1.18)); bpy.context.object.data.materials.append(linen)
# physically based soft sources
light("Warm ceiling softbox",(0,1,4.9),900,(1,.72,.48),5,(0,0,0)); light("Cool window moonlight",(0,-4.7,4),1150,(.32,.48,1),4,(0,0,1)); firelight=light("Fire bounce",(-4.0,1.5,1.1),190,(1,.2,.05),1.1,(0,0,1)); light("Warm room fill",(1.5,3.7,3.6),350,(1,.65,.38),3,(0,0,1))
# camera is genuinely moving through the modeled space
bpy.ops.object.camera_add(location=(.3,-1.3,2.05)); cam=bpy.context.object; cam.data.lens=30; aim(cam,(0,1,1.35)); bpy.context.scene.camera=cam
cam.location=(.3,-1.3,2.05); aim(cam,(0,1,1.35)); cam.keyframe_insert(data_path="location",frame=1); cam.keyframe_insert(data_path="rotation_euler",frame=1)
cam.location=(-.12,-.1,2.0); aim(cam,(0,1.2,1.35)); cam.keyframe_insert(data_path="location",frame=721); cam.keyframe_insert(data_path="rotation_euler",frame=721)
for fc in cam.animation_data.action.fcurves:
 for k in fc.keyframe_points: k.interpolation="BEZIER"
scene=bpy.context.scene; scene.render.engine="BLENDER_EEVEE_NEXT" if bpy.app.version >= (4,2,0) else "BLENDER_EEVEE"; scene.eevee.taa_render_samples=32; scene.render.resolution_x=720; scene.render.resolution_y=1280; scene.render.resolution_percentage=100; scene.render.fps=24; scene.frame_start=1; scene.frame_end=721; scene.render.image_settings.file_format="PNG"; scene.render.filepath=os.path.join(out,"frame_"); scene.view_settings.view_transform="AgX"; scene.world.color=(.012,.018,.035); scene.camera.data.dof.use_dof=True; scene.camera.data.dof.focus_distance=5; scene.camera.data.dof.aperture_fstop=8
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,"tv_off_luxury_lounge.blend")); bpy.ops.render.render(animation=True)

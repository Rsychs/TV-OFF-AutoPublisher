#!/usr/bin/env python3
"""Build a cinematic, physically lit 3D living room plate for TV OFF Shorts."""
import bpy, math, os, subprocess, json
from mathutils import Vector
from pathlib import Path

OUT=Path("output"); OUT.mkdir(exist_ok=True)
# Clean scene
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
for datablocks in (bpy.data.materials, bpy.data.curves, bpy.data.cameras, bpy.data.lights):
    pass

def mat(name, color, metallic=0.0, rough=.5, emission=None, strength=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get("Principled BSDF"); p.inputs["Base Color"].default_value=(*color,1)
    p.inputs["Metallic"].default_value=metallic; p.inputs["Roughness"].default_value=rough
    if emission:
        p.inputs["Emission Color"].default_value=(*emission,1); p.inputs["Emission Strength"].default_value=strength
    return m

navy=mat("Midnight blue velvet",(.055,.075,.12),rough=.9)
wall=mat("Warm midnight plaster",(.075,.065,.075),rough=.95)
floor=mat("Honey oak",(.12,.075,.045),rough=.42)
black=mat("Matte black metal",(.008,.012,.02),metallic=.55,rough=.28)
screen=mat("TV warm ambient glow",(.025,.055,.11),rough=.2,emission=(.035,.12,.28),strength=1.25)
brass=mat("Brushed warm brass",(.34,.2,.075),metallic=.8,rough=.25)
cream=mat("Warm ivory linen",(.62,.48,.32),rough=.95)
pillow=mat("Soft caramel cushions",(.38,.19,.09),rough=.98)
glass=mat("Night window",(.012,.025,.055),rough=.15,metallic=.25)
green=mat("Plant leaves",(.018,.11,.075),rough=.8)

def cube(name, loc, scale, material, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=name
    o.dimensions=scale; bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material: o.data.materials.append(material)
    if bevel:
        mod=o.modifiers.new("Soft crafted edges","BEVEL"); mod.width=bevel; mod.segments=4
        o.modifiers.new("Weighted corner normals","WEIGHTED_NORMAL")
    return o

def uv(name,loc,scale,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, location=loc); o=bpy.context.object
    o.name=name; o.scale=scale; o.data.materials.append(material); bpy.ops.object.shade_smooth(); return o

def area(name,loc,power,color,size,target):
    bpy.ops.object.light_add(type="AREA", location=loc); l=bpy.context.object; l.name=name
    l.data.energy=power; l.data.color=color; l.data.shape="DISK"; l.data.size=size
    l.rotation_euler=(Vector(target)-l.location).to_track_quat("-Z","Y").to_euler()

# Room shell and floor
cube("Oak floor",(0,1,-.12),(8,10,.24),floor,.04)
cube("Back wall",(0,3.8,2.6),(8,.22,5.2),wall,.04)
cube("Left wall",(-4,0,2.6),(.22,8,5.2),wall,.04)
# Window, frame and distant night city
cube("Window glass",(-2.65,3.66,2.65),(1.7,.035,2.45),glass,.025)
for x in [-3.53,-2.65,-1.77]: cube("Window mullion",(x,3.61,2.65),(.045,.09,2.52),brass,.012)
for z in [1.42,2.65,3.88]: cube("Window rail",(-2.65,3.61,z),(1.82,.09,.045),brass,.012)
for i,(x,h,w) in enumerate([(-3.35,1.0,.24),(-3.05,1.55,.28),(-2.72,.8,.2),(-2.42,1.3,.25),(-2.1,.95,.22)]):
    cube("Distant skyline", (x,3.63,1.45+h/2),(w,.025,h),black,.01)
# TV console and large screen
cube("Media console",(0,3.22,.42),(3.55,.62,.72),black,.08)
cube("Console wood front",(0,2.895,.42),(3.35,.025,.52),navy,.025)
for x in [-1.15,0,1.15]:
    cube("Console drawer",(x,2.875,.43),(.88,.025,.32),brass,.012)
cube("TV bezel",(0,3.36,2.35),(3.65,.16,2.12),black,.075)
cube("TV glass",(0,3.265,2.35),(3.48,.025,1.95),screen,.025)
# Sofa: upholstered base, back, arms and cushions
cube("Sofa base",(0,-1.25,.52),(4.25,1.45,.68),navy,.22)
cube("Sofa back",(0,-.48,1.25),(4.15,.48,1.65),navy,.22)
for x in [-1.95,1.95]: cube("Sofa arm",(x,-1.15,.95),(.48,1.55,1.0),navy,.18)
for x in [-1.05,0,1.05]:
    cube("Seat cushion",(x,-1.37,.91),(1.15,1.0,.22),pillow,.12)
    c=cube("Back cushion",(x,-.72,1.53),(1.08,.24,.88),pillow,.13); c.rotation_euler[1]=(-.05 if x<0 else .05)
# Cozy layered textiles and warm details
throw=mat("Chunky knit throw",(.48,.29,.16),rough=1.0)
cube("Draped sofa throw",(-1.15,-1.25,1.12),(.82,1.05,.12),throw,.16)
cube("Side table",(2.85,-1.0,.48),(.72,.72,.9),floor,.1)
candle=mat("Candle flame",(.9,.35,.08),rough=.25,emission=(1.0,.22,.035),strength=3.0)
bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.095,depth=.28,location=(2.85,-1.0,1.07))
bpy.context.object.data.materials.append(cream)
uv("Candle flame",(2.85,-1.0,1.26),(.035,.035,.09),candle)
# Coffee table and rug
cube("Soft wool rug",(0,-2.55,.015),(4.9,2.0,.035),cream,.08)
cube("Coffee table top",(0,-2.55,.48),(2.5,1.05,.12),floor,.12)
for x in [-1,1]: cube("Table leg",(x,-2.55,.23),(.07,.07,.45),brass,.02)
# Floor lamp with warm shade
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=.035, depth=2.25, location=(2.8,1.45,1.12))
bpy.context.object.data.materials.append(brass)
uv("Lamp shade",(2.8,1.45,2.28),(.38,.38,.28),cream)
area("Warm floor lamp",(2.8,1.35,2.2),360,(1.0,.55,.25),1.8,(1.8,1.8,0.8))
# Plant pot and leaves
bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=.28, radius2=.19, depth=.48, location=(-3.15,1.65,.25))
bpy.context.object.data.materials.append(black)
for i in range(9):
    ang=i*2.4; x=-3.15+math.cos(ang)*(.18+(i%3)*.09); y=1.65+math.sin(ang)*(.18+(i%3)*.09)
    leaf=uv("Ficus leaf",(x,y,.85+(i%4)*.18),(.12,.08,.48),green); leaf.rotation_euler[1]=math.cos(ang)*.45; leaf.rotation_euler[0]=math.sin(ang)*.35
# Lighting
area("Cool window fill",(-2.5,2.9,3.4),180,(.22,.34,.75),3.0,(0,0,1))
area("Soft warm ceiling bounce",(0,0,4.7),680,(1.0,.68,.42),4.5,(0,1,0))
area("Warm sofa rim",(3,-.2,2.9),420,(1.0,.55,.28),2.5,(0,-1,1))
# Camera portrait framing
bpy.ops.object.camera_add(location=(0,-9.2,2.8)); cam=bpy.context.object
cam.rotation_euler=(Vector((0,1.0,1.75))-cam.location).to_track_quat("-Z","Y").to_euler()
cam.data.lens=38; cam.data.sensor_width=36; cam.data.sensor_fit="VERTICAL"; bpy.context.scene.camera=cam
scene=bpy.context.scene
scene.render.engine="BLENDER_EEVEE"
scene.eevee.taa_render_samples=64
scene.render.resolution_x=720; scene.render.resolution_y=1280; scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"; scene.render.film_transparent=False
scene.world.color=(.10,.075,.055)
scene.view_settings.view_transform="AgX"
scene.render.filepath=str(OUT/"room_scene.png")
# gentle bloom via compositor
scene.use_nodes=True; nt=scene.node_tree; nt.nodes.clear()
rl=nt.nodes.new("CompositorNodeRLayers"); glare=nt.nodes.new("CompositorNodeGlare"); glare.glare_type="FOG_GLOW"; glare.threshold=1.1; glare.quality="HIGH"
comp=nt.nodes.new("CompositorNodeComposite"); nt.links.new(rl.outputs["Image"],glare.inputs["Image"]); nt.links.new(glare.outputs["Image"],comp.inputs["Image"])
bpy.ops.render.render(write_still=True)
print("BLENDER_ROOM_RENDER_COMPLETE")

# Pone al lagarto riggeado (Tripo) un rig completo y sus animaciones, y lo exporta a GLB para three.js.
#   Blender --background --factory-startup --python animar.py -- lagarto-rig.glb lagarto.glb [previas/]
# Huesos que se añaden al rig de Tripo: cola (5), mandíbula, gafas (cejas) y 2 huesos por dedo (3 dedos por mano).
# Clips: Idle (bucle) · Saludo · Coger · Guardar · Adios.
# Las poses se escriben como DIRECCIONES de cada hueso en el espacio del personaje (adelante / arriba / lado):
# así no hay que adivinar los ejes locales que Tripo le dio a cada hueso.
import bpy, sys, math, os
from mathutils import Vector, Matrix, Quaternion

args = sys.argv[sys.argv.index("--") + 1:]
ORIGEN, DESTINO = args[0], args[1]
PREVIAS = args[2] if len(args) > 2 else None
FPS = 24

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=ORIGEN)
sc = bpy.context.scene; sc.render.fps = FPS
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
malla = max((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: len(o.data.vertices))
for o in [o for o in bpy.data.objects if o.type == "MESH" and o is not malla]: bpy.data.objects.remove(o)   # la icosfera suelta de Tripo
bpy.context.view_layer.objects.active = arm

# ---------- ejes del personaje ----------
U = Vector((0, 0, 1))
B = arm.data.bones
pie = B["L_ToeBase"].tail_local - B["L_Foot"].head_local
F = Vector((1, 0, 0)) if pie.x > 0 else Vector((-1, 0, 0))          # los pies apuntan hacia delante
LADO_L = Vector((0, 1, 0)) if B["L_Hand"].head_local.y > 0 else Vector((0, -1, 0))
LADO_R = -LADO_L
print("adelante", F, "lado izquierdo", LADO_L)

# ---------- la malla en el espacio de los huesos (Tripo la guarda en otro sistema) ----------
dg = bpy.context.evaluated_depsgraph_get()
ev = malla.evaluated_get(dg).data
P = [v.co.copy() for v in ev.vertices]
grupos = {g.index: g.name for g in malla.vertex_groups}
def peso(i, n):
    for g in malla.data.vertices[i].groups:
        if grupos[g.group] == n: return g.weight
    return 0.0
def pon(i, n, w):
    if n not in malla.vertex_groups: malla.vertex_groups.new(name=n)
    malla.vertex_groups[n].add([i], max(0.0, w), "REPLACE")
# color de la textura por vértice: con él se encuentran la lengua (roja) y las gafas (negras)
mat = malla.data.materials[0]; img = next(n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image)
IW, IH = img.size; px = img.pixels[:]; uv = malla.data.uv_layers.active.data
col = [None] * len(P)
for poly in malla.data.polygons:
    for li in poly.loop_indices:
        vi = malla.data.loops[li].vertex_index
        if col[vi] is None:
            u, v = uv[li].uv; x = int(u % 1 * (IW - 1)); y = int(v % 1 * (IH - 1)); k = (y * IW + x) * 4; col[vi] = (px[k], px[k + 1], px[k + 2])
def es_negro(i): return col[i] is not None and max(col[i]) < .16
def es_rojo(i): return col[i] is not None and col[i][0] > .55 and col[i][1] < .25 and col[i][2] < .3
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))

hipx = B["Hip"].head_local.x
atras = -F.x
# ---------- 1) cola ----------
N_COLA = 5
def es_cola(co): return (co.x - hipx) * atras > .13 and co.z < .5
cola_idx = [i for i, co in enumerate(P) if es_cola(co)]
cs = [(P[i] - Vector((hipx, 0, 0))).dot(Vector((atras, 0, 0))) for i in cola_idx]
lmax = max(cs); tramos = []
for k in range(N_COLA + 1):
    d0, d1 = lmax * k / N_COLA - lmax / N_COLA * .5, lmax * k / N_COLA + lmax / N_COLA * .5
    sel = [P[i] for i, c in zip(cola_idx, cs) if d0 <= c < d1]
    if len(sel) < 6: sel = [P[i] for i, c in sorted(zip(cola_idx, cs), key=lambda ic: abs(ic[1] - lmax * k / N_COLA))[:30]]
    tramos.append(sum(sel, Vector()) / len(sel))
tramos[0] = Vector((hipx + atras * .06, tramos[0].y * .5, min(tramos[0].z, B["Hip"].head_local.z - .02)))

# ---------- 2) boca, gafas y dedos: dónde están ----------
lengua = [i for i in range(len(P)) if es_rojo(i) and P[i].z > .55 and (P[i].x - hipx) * F.x > .1]
zboca = sum(P[i].z for i in lengua) / len(lengua)                       # línea de la boca
xboca0 = min((P[i].x - hipx) * F.x for i in lengua)                     # dónde empieza la boca (hacia atrás)
gafas = [i for i in range(len(P)) if es_negro(i) and P[i].z > .72 and (P[i].x - hipx) * F.x > .08]
zg0, zg1 = min(P[i].z for i in gafas), max(P[i].z for i in gafas)
print("boca z", round(zboca, 3), "x0", round(xboca0, 3), "gafas z", round(zg0, 3), round(zg1, 3))

def kmedias(idx, k=3, it=25):
    pts = [P[i].x for i in idx]; lo, hi = min(pts), max(pts)
    cen = [lo + (hi - lo) * (j + .5) / k for j in range(k)]
    for _ in range(it):
        asg = [min(range(k), key=lambda j: abs(p - cen[j])) for p in pts]
        for j in range(k):
            m = [p for p, a in zip(pts, asg) if a == j]
            if m: cen[j] = sum(m) / len(m)
    return [[idx[n] for n, a in enumerate(asg) if a == j] for j in range(k)]
DEDOS = {}   # lado → [(nombre_base, nombre_punta, idx, base_pt, mid_pt, tip_pt)]
for lado in ("R", "L"):
    hb = B[lado + "_Hand"]; d = (hb.tail_local - hb.head_local).normalized(); L = (hb.tail_local - hb.head_local).length
    mano_idx = [i for i in range(len(P)) if peso(i, lado + "_Hand") > .35]
    dedos = [i for i in mano_idx if (P[i] - hb.head_local).dot(d) > L * .45]
    cl = sorted([c for c in kmedias(dedos) if c], key=lambda c: (sum(P[i].x for i in c) / len(c)) * F.x)   # de atrás a delante
    lista = []
    for n, c in enumerate(cl):
        cen = sum((P[i] for i in c), Vector()) / len(c)
        tip = max((P[i] for i in c), key=lambda p: (p - hb.head_local).dot(d))
        medio_mano = hb.head_local + d * L * .5
        base = Vector((medio_mano.x + (cen.x - medio_mano.x) * .6, medio_mano.y, medio_mano.z))
        mid = base.lerp(tip, .55)
        lista.append((f"{lado}_Dedo{n+1}_1", f"{lado}_Dedo{n+1}_2", c, base, mid, tip + d * .006))
    DEDOS[lado] = lista
print("dedos", {k: [(x[0], len(x[2])) for x in v] for k, v in DEDOS.items()})

# ---------- 3) crear los huesos ----------
bpy.ops.object.mode_set(mode="EDIT")
EB = arm.data.edit_bones
padre = EB["Hip"]; nombres_cola = []
for k in range(N_COLA):
    b = EB.new(f"Cola0{k+1}"); b.head = tramos[k]; b.tail = tramos[k + 1]; b.parent = padre; b.use_connect = k > 0; padre = b; nombres_cola.append(b.name)
mand = EB.new("Mandibula"); mand.head = Vector((hipx + F.x * (xboca0 - .02), 0, zboca - .01)); mand.tail = Vector((hipx + F.x * (xboca0 + .2), 0, zboca - .07)); mand.parent = EB["Head"]
gaf = EB.new("Gafas"); gaf.head = Vector((hipx + F.x * .1, 0, (zg0 + zg1) / 2)); gaf.tail = Vector((hipx + F.x * .3, 0, (zg0 + zg1) / 2 + .02)); gaf.parent = EB["Head"]
for lado, lista in DEDOS.items():
    for n1, n2, c, base, mid, tip in lista:
        b1 = EB.new(n1); b1.head = base; b1.tail = mid; b1.parent = EB[lado + "_Hand"]
        b2 = EB.new(n2); b2.head = mid; b2.tail = tip; b2.parent = b1; b2.use_connect = True
bpy.ops.object.mode_set(mode="OBJECT")
for n in nombres_cola + ["Mandibula", "Gafas"] + [x for l in DEDOS.values() for t in l for x in t[:2]]:
    if n not in malla.vertex_groups: malla.vertex_groups.new(name=n)
grupos = {g.index: g.name for g in malla.vertex_groups}

# ---------- 4) pesos ----------
def traslada(i, a, w):
    """pasa una fracción `w` de TODO el peso del vértice i al grupo `a`"""
    if w <= 0: return
    total = sum(g.weight for g in malla.data.vertices[i].groups)
    if total <= 0: return
    for g in list(malla.data.vertices[i].groups):
        n = grupos[g.group]
        if n != a: malla.vertex_groups[n].add([i], g.weight * (1 - w), "REPLACE")
    pon(i, a, w * total)
# cola
for i, c in zip(cola_idx, cs):
    t = c / lmax * N_COLA; k = min(N_COLA - 1, int(t)); f = t - k
    base = clamp(((P[i].x - hipx) * atras - .13) / .10)
    for g in list(malla.data.vertices[i].groups):
        n = grupos[g.group]
        if n not in nombres_cola: malla.vertex_groups[n].add([i], g.weight * (1 - base), "REPLACE")
    pon(i, nombres_cola[k], (1 - f) * base)
    if k + 1 < N_COLA: pon(i, nombres_cola[k + 1], f * base)
    else: pon(i, nombres_cola[k], base)
# mandíbula: lo que queda por debajo de la línea de la boca y delante del pivote, con fundido hacia arriba
for i in range(len(P)):
    if peso(i, "Head") < .3: continue
    xf = (P[i].x - hipx) * F.x
    if xf < xboca0 - .04: continue
    w = clamp((zboca + .012 - P[i].z) / .03) * clamp((xf - (xboca0 - .04)) / .04)
    if es_rojo(i) and P[i].z < zboca + .01: w = max(w, .9)        # la lengua va con la mandíbula
    traslada(i, "Mandibula", w)
# gafas: la montura entera y un poco de la piel de alrededor, para que suban con las cejas
for i in range(len(P)):
    if peso(i, "Head") < .3 and not es_negro(i): continue
    xf = (P[i].x - hipx) * F.x
    if xf < .06 or P[i].z < zg0 - .025 or P[i].z > zg1 + .03: continue
    w = 1.0 if (es_negro(i) and P[i].z >= zg0 - .005) else .45 * clamp(1 - abs(P[i].z - (zg0 + zg1) / 2) / ((zg1 - zg0) / 2 + .03))
    traslada(i, "Gafas", w)
# dedos: a partir de la mitad de la mano, cada dedo a su cadena, con fundido en la raíz
for lado, lista in DEDOS.items():
    hb = B[lado + "_Hand"]; d = (hb.tail_local - hb.head_local).normalized(); L = (hb.tail_local - hb.head_local).length
    for n1, n2, c, base, mid, tip in lista:
        eje = (tip - base); largo = eje.length; eje.normalize()
        for i in c:
            a = (P[i] - hb.head_local).dot(d)
            raiz = clamp((a - L * .45) / (L * .15))
            t = clamp((P[i] - base).dot(eje) / largo)
            w1 = (1 - clamp((t - .45) / .3)); w2 = 1 - w1
            total = sum(g.weight for g in malla.data.vertices[i].groups) or 1
            for g in list(malla.data.vertices[i].groups):
                n = grupos[g.group]
                if n not in (n1, n2): malla.vertex_groups[n].add([i], g.weight * (1 - raiz), "REPLACE")
            pon(i, n1, w1 * raiz * total); pon(i, n2, w2 * raiz * total)
# normaliza todo
for v in malla.data.vertices:
    tot = sum(g.weight for g in v.groups)
    if tot > 0 and abs(tot - 1) > 1e-4:
        for g in list(v.groups): malla.vertex_groups[grupos[g.group]].add([v.index], g.weight / tot, "REPLACE")
print("rig completo:", len(arm.data.bones), "huesos")

# ---------- 5) posar ----------
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="POSE")
PB = arm.pose.bones
def dir_reposo(nombre):
    b = PB[nombre].bone
    return (b.tail_local - b.head_local).normalized()
REST_Q = {}
for pb in PB:
    pb.rotation_mode = "QUATERNION"
    REST_Q[pb.name] = pb.bone.matrix_local.to_quaternion()

def apunta(nombre, direccion, giro=0.0, mueve=None):
    """Orienta el hueso para que apunte a `direccion` (espacio del personaje), con giro sobre su eje y desplazamiento opcional."""
    pb = PB[nombre]
    bpy.context.view_layer.update()
    d = Vector(direccion).normalized()
    r = dir_reposo(nombre)
    q = r.rotation_difference(d)
    if giro: q = Quaternion(d, giro) @ q
    rot = (q @ REST_Q[nombre]).to_matrix().to_4x4()
    m = pb.matrix.copy()
    rot.translation = m.translation + (Vector(mueve) if mueve else Vector())
    pb.matrix = rot
    bpy.context.view_layer.update()

def reposo(nombre):
    PB[nombre].rotation_quaternion = Quaternion((1, 0, 0, 0)); PB[nombre].location = (0, 0, 0); PB[nombre].scale = (1, 1, 1)

NOMBRES_DEDOS = [x for l in DEDOS.values() for t in l for x in t[:2]]
ORDEN = ["Hip", "Waist", "Spine01", "Spine02", "NeckTwist01", "NeckTwist02", "Head", "Mandibula", "Gafas",
         "L_Clavicle", "L_Upperarm", "L_Forearm", "L_Hand", "R_Clavicle", "R_Upperarm", "R_Forearm", "R_Hand",
         "L_Thigh", "L_Calf", "L_Foot", "R_Thigh", "R_Calf", "R_Foot"] + NOMBRES_DEDOS
TODOS = [pb.name for pb in PB]
def dirs(ad=0, ar=0, la=0, lado=None):
    return (F * ad + U * ar + ((lado or LADO_L) * la)).normalized()
def mov(ad=0, ar=0, la=0): return F * ad + U * ar + LADO_L * la

# ---- gestos compuestos ----
COLA = {"amp": .12, "f": .55, "pitch": 0.0, "arrastre": 0.0}
def dir_cola(k, frame):
    r = dir_reposo(nombres_cola[k])
    fase = frame / FPS * COLA["f"] * 2 * math.pi - k * .9
    yaw = COLA["amp"] * (0.35 + k * .25) * math.sin(fase) + COLA["arrastre"] * (k + 1) / N_COLA
    pitch = COLA["pitch"] * (k + 1) / N_COLA + .03 * math.sin(fase * 2 + 1) * k / N_COLA
    return (Quaternion(U, yaw) @ Quaternion(U.cross(r).normalized(), pitch)) @ r
# Cara y dedos se posan EN LOCAL (respecto a su padre): así la boca y las gafas acompañan a la cabeza y los dedos a la mano.
def q_local(nombre, eje_mundo, ang): return Quaternion(REST_Q[nombre].inverted() @ Vector(eje_mundo), ang)
def v_local(nombre, off_mundo): return REST_Q[nombre].inverted() @ Vector(off_mundo)
def boca(apertura):
    """0 = cerrada (la sonrisa del logo) · 1 = muy abierta. En reposo ya está medio abierta (0,35)."""
    return ("LOCAL", q_local("Mandibula", LADO_L, (apertura - .35) * .45 * F.x), None)
def cejas(sube):
    """las gafas suben/bajan un poco y cabecean: hace de cejas"""
    return {"Gafas": ("LOCAL", q_local("Gafas", LADO_L, -.05 * sube * F.x), v_local("Gafas", mov(ar=.012 * sube, ad=-.003 * sube)))}
def mano(lado, cierre=0.0, abre=0.0, pulgar=False, indice=False):
    """cierre 0..1 curva los dedos hacia la palma; abre separa los dedos; pulgar = el delantero estirado hacia arriba; indice = el delantero estirado y el resto cerrado"""
    out = {}; L = LADO_L if lado == "L" else LADO_R; s = 1   # comprobado en render: las dos manos cierran hacia la palma con el mismo signo
    for n, (n1, n2, *_r) in enumerate(DEDOS[lado]):
        sep = (n - 1) * abre * .35
        if indice:
            if n == len(DEDOS[lado]) - 1: out[n1] = ("LOCAL", q_local(n1, LADO_L, .15 * F.x), None); out[n2] = ("LOCAL", q_local(n2, LADO_L, 0), None); continue
            cierre = .95
        if pulgar and n == len(DEDOS[lado]) - 1:
            out[n1] = ("LOCAL", q_local(n1, L, -1.2 * F.x), None); out[n2] = ("LOCAL", q_local(n2, L, -.6 * F.x), None); continue
        # la palma mira hacia delante: cerrar = las puntas van hacia delante (giro sobre el eje lateral); separar = giro sobre el eje delantero
        out[n1] = ("LOCAL", q_local(n1, LADO_L, -cierre * .9 * F.x) @ q_local(n1, F, sep * s), None)
        out[n2] = ("LOCAL", q_local(n2, LADO_L, -cierre * 1.5 * F.x), None)
    return out

def _puntos_pie(lado):
    pf, pt = PB[lado + "_Foot"], PB[lado + "_ToeBase"]
    return [pf.head.z, pf.tail.z, pt.tail.z]
Z_PIE = min(B["L_Foot"].head_local.z, B["L_Foot"].tail_local.z, B["L_ToeBase"].tail_local.z, B["R_Foot"].head_local.z, B["R_Foot"].tail_local.z, B["R_ToeBase"].tail_local.z)
print("altura del pie en reposo", round(Z_PIE, 4))

def suela_min(levanta=None):
    """altura mínima de la MALLA deformada (la suela de verdad), sin contar el pie levantado"""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); ev = malla.evaluated_get(dg).data
    if levanta:
        g = malla.vertex_groups[levanta + "_Foot"].index; g2 = malla.vertex_groups[levanta + "_ToeBase"].index; gc = malla.vertex_groups[levanta + "_Calf"].index
        pies = set(v.index for v in malla.data.vertices if any(x.group in (g, g2, gc) and x.weight > .3 for x in v.groups))
        return min(v.co.z for v in ev.vertices if v.index not in pies)
    return min(v.co.z for v in ev.vertices)

def planta_pies(levanta=None):
    """desplaza la cadera en vertical hasta que la suela apoyada toca el suelo (z = 0): dos pasadas, hueso y malla"""
    bpy.context.view_layer.update()
    apoyados = [l for l in ("L", "R") if l != levanta]
    zmin = min(z for l in apoyados for z in _puntos_pie(l))
    PB["Hip"].matrix = Matrix.Translation(U * (Z_PIE - zmin)) @ PB["Hip"].matrix; bpy.context.view_layer.update()
    for _ in range(2):   # ajuste fino con la malla real
        z = suela_min(levanta)
        if abs(z) < 5e-4: break
        PB["Hip"].matrix = Matrix.Translation(U * (-z)) @ PB["Hip"].matrix; bpy.context.view_layer.update()

def rellena_suelo(frames, levanta_en=(), cada=2):
    """entre claves, la interpolación hunde el pie: se hornea la altura de la cadera cada pocos fotogramas"""
    for f in range(0, frames + 1, cada):
        sc.frame_set(f); lev = next((l for a, b, l in levanta_en if a <= f <= b), None)
        planta_pies(lev); PB["Hip"].keyframe_insert("location", frame=f)

def clave(frame, poses, cadera=None, respira=0.0, apoyo=0.0, levanta=None):
    """poses: {hueso: direccion | (direccion, giro) | (direccion, giro, mueve)}. Lo que no se nombra queda en reposo.
       cadera: desplazamiento (vector). respira: 0..1 hincha el pecho. apoyo: -1..1 carga el peso en un pie (+ izquierdo)."""
    sc.frame_set(frame)
    for n in TODOS:
        if n not in poses: reposo(n)
    bpy.context.view_layer.update()
    desplaza = (Vector(cadera) if cadera else Vector()) + LADO_L * apoyo * .018
    for n in ORDEN:
        if n in poses and poses[n] is not None:
            p = poses[n]
            if n == "Hip": apunta(n, p[0] if isinstance(p, tuple) else p, mueve=desplaza); continue
            if isinstance(p, tuple) and p[0] == "LOCAL":
                PB[n].rotation_quaternion = p[1]
                if p[2] is not None: PB[n].location = p[2]
                bpy.context.view_layer.update(); continue
            if isinstance(p, tuple): apunta(n, p[0], p[1] if len(p) > 1 else 0.0, mueve=p[2] if len(p) > 2 else None)
            else: apunta(n, p)
    if "Hip" not in poses and desplaza.length > 0: apunta("Hip", dir_reposo("Hip"), mueve=desplaza)
    if apoyo:   # el peso en un pie: la otra pierna algo doblada
        otro = "R" if apoyo > 0 else "L"; LO = LADO_L if otro == "L" else LADO_R
        if otro + "_Thigh" not in poses: apunta(otro + "_Thigh", dirs(ad=.12, ar=-.95, la=.05, lado=LO)); apunta(otro + "_Calf", dirs(ad=-.1, ar=-.98))
    # pies apoyados planos y clavados al suelo: la cadera sube o baja lo que haga falta (foot planting)
    for lado in ("L", "R"):
        if lado != levanta and lado + "_Foot" not in poses: apunta(lado + "_Foot", dir_reposo(lado + "_Foot"))
    planta_pies(levanta)
    for k in range(N_COLA): apunta(nombres_cola[k], dir_cola(k, frame))
    s = 1 + .028 * respira
    PB["Spine01"].scale = (s, s, s); PB["Spine02"].scale = (1 + .012 * respira,) * 3
    for n in TODOS:
        PB[n].keyframe_insert("rotation_quaternion", frame=frame); PB[n].keyframe_insert("location", frame=frame); PB[n].keyframe_insert("scale", frame=frame)

def rellena_cola(frames, cada=4):
    for f in range(0, frames + 1, cada):
        sc.frame_set(f)
        for k in range(N_COLA): apunta(nombres_cola[k], dir_cola(k, f)); PB[nombres_cola[k]].keyframe_insert("rotation_quaternion", frame=f)

acciones = {}
def accion(nombre, dur_s):
    ac = bpy.data.actions.new(nombre)
    arm.animation_data_create(); arm.animation_data.action = ac
    if hasattr(ac, "slots"):
        slot = ac.slots.new(id_type="OBJECT", name=arm.name); arm.animation_data.action_slot = slot
    acciones[nombre] = (ac, int(dur_s * FPS))
    return ac

BRAZOS = {"L_Upperarm": dirs(ad=.05, ar=-.95, la=.3), "R_Upperarm": dirs(ad=.05, ar=-.95, la=.3, lado=LADO_R)}
def base(**extra):
    d = dict(BRAZOS); d["Mandibula"] = boca(.35); d.update(mano("L", .15)); d.update(mano("R", .15)); d.update(extra); return d

# ---------- Idle (3,2 s, bucle): respira, cambia el peso de pie, mira alrededor, la cola se mece ----------
accion("Idle", 3.2); COLA.update(amp=.16, f=1 / 3.2, pitch=0, arrastre=0)
for f, k, ap, mira, ceja in [(0, 0, .0, (0, 0), 0), (19, 1, .6, (.05, .06), 0), (38, 0, 1.0, (.02, -.04), 1), (57, 1, .4, (-.03, .05), 0), (76, 0, 0, (0, 0), 0)]:
    clave(f, base(Spine02=dirs(ad=.04 * k, ar=1), Head=dirs(ad=.06 + mira[0], ar=1, la=mira[1]), Mandibula=boca(.3 + .1 * k), **cejas(ceja)), respira=k, apoyo=ap)
rellena_cola(76); rellena_suelo(76)

# ---------- Saludo (2 s): anticipación, brazo arriba, agita la mano con los dedos abiertos y «habla» ----------
accion("Saludo", 2.0); COLA.update(amp=.22, f=1.1, pitch=.05, arrastre=0)
def sal(k, habla):
    return base(Spine02=dirs(ad=.03, ar=1, la=-.04 * k, lado=LADO_R), Head=dirs(ad=.12, ar=1, la=.08, lado=LADO_R), Mandibula=boca(habla),
                R_Upperarm=dirs(ad=.25, ar=.75, la=.6, lado=LADO_R), R_Forearm=dirs(ad=.15, ar=1, la=.1, lado=LADO_R), R_Hand=dirs(ad=.1, ar=1, la=k, lado=LADO_R),
                **mano("R", 0, abre=1), **cejas(1))
clave(0, base(), apoyo=.3)
clave(6, base(**cejas(1), Mandibula=boca(.6), R_Upperarm=dirs(ad=.5, ar=.2, la=.6, lado=LADO_R), R_Forearm=dirs(ad=.3, ar=.95, la=.2, lado=LADO_R)), apoyo=.3)
clave(11, sal(-.35, .8), apoyo=.4); clave(17, sal(.45, .3), apoyo=.4); clave(23, sal(-.45, .8), apoyo=.4); clave(29, sal(.45, .3), apoyo=.4); clave(35, sal(0, .6), apoyo=.3)
clave(42, base(Head=dirs(ad=.08, ar=1), **cejas(.3)), apoyo=.2)
clave(48, base(), apoyo=0)
rellena_cola(48); rellena_suelo(48)

# ---------- Coger (2,4 s): mira la maleta, dobla rodillas y espalda, abre las manos, cierra sobre el asa y se incorpora ----------
accion("Coger", 2.4); COLA.update(amp=.08, f=.6, pitch=.12, arrastre=0)
clave(0, base(Head=dirs(ad=.5, ar=.85), **cejas(.6)))
piernas_flex = {"L_Thigh": dirs(ad=.55, ar=-.8, la=.1), "L_Calf": dirs(ad=-.55, ar=-.8), "R_Thigh": dirs(ad=.55, ar=-.8, la=.1, lado=LADO_R), "R_Calf": dirs(ad=-.55, ar=-.8)}
agachado = base(Hip=dirs(ad=-.2, ar=1), Spine01=dirs(ad=.75, ar=.65), Spine02=dirs(ad=.6, ar=.8), Head=dirs(ad=.75, ar=.65), Mandibula=boca(.5),
                L_Upperarm=dirs(ad=.5, ar=-.85, la=.15), L_Forearm=dirs(ad=.75, ar=-.65, la=.05), L_Hand=dirs(ad=.9, ar=-.4),
                R_Upperarm=dirs(ad=.5, ar=-.85, la=.15, lado=LADO_R), R_Forearm=dirs(ad=.75, ar=-.65, la=.05, lado=LADO_R), R_Hand=dirs(ad=.9, ar=-.4, lado=LADO_R),
                **piernas_flex, **mano("L", 0, abre=.8), **mano("R", 0, abre=.8))
clave(12, dict(agachado, Spine01=dirs(ad=.4, ar=.9), Head=dirs(ad=.6, ar=.8)))
clave(21, agachado)
clave(27, dict(agachado, **mano("L", .95), **mano("R", .95), Mandibula=boca(.2)))   # agarra
sostiene = base(Spine01=dirs(ad=.05, ar=1), Spine02=dirs(ad=.02, ar=1), Head=dirs(ad=.15, ar=1), Mandibula=boca(.4),
                L_Upperarm=dirs(ad=.45, ar=-.85, la=.15), L_Forearm=dirs(ad=.95, ar=-.2, la=-.15), L_Hand=dirs(ad=1, ar=-.1, la=-.2),
                R_Upperarm=dirs(ad=.45, ar=-.85, la=.15, lado=LADO_R), R_Forearm=dirs(ad=.95, ar=-.2, la=-.15, lado=LADO_R), R_Hand=dirs(ad=1, ar=-.1, la=-.2, lado=LADO_R),
                **mano("L", .95), **mano("R", .95))
clave(38, dict(sostiene, Spine01=dirs(ad=.25, ar=.95), **piernas_flex), respira=.5)   # el esfuerzo
clave(48, sostiene, respira=.3); clave(57, sostiene)
rellena_cola(57); rellena_suelo(57)

# ---------- Guardar (2,6 s): da un paso hacia la taquilla, levanta la maleta, la empuja dentro, suelta y mira ----------
accion("Guardar", 2.6); COLA.update(amp=.1, f=.7, pitch=-.08, arrastre=.25)
clave(0, sostiene)
paso1 = dict(sostiene, L_Thigh=dirs(ad=.45, ar=-.9, la=.08), L_Calf=dirs(ad=-.2, ar=-.98), L_Foot=dirs(ad=1, ar=.15), Head=dirs(ad=.5, ar=.85), Mandibula=boca(.3))
clave(8, paso1, cadera=mov(ad=.04), apoyo=-.6, levanta="L")
paso2 = dict(sostiene, R_Thigh=dirs(ad=.4, ar=-.9, la=.08, lado=LADO_R), R_Calf=dirs(ad=-.2, ar=-.98), Head=dirs(ad=.6, ar=.8))
clave(16, paso2, cadera=mov(ad=.1), apoyo=.6, levanta="R")
alto = base(Spine01=dirs(ad=.08, ar=1), Spine02=dirs(ad=.08, ar=1), Head=dirs(ad=.6, ar=.8), Mandibula=boca(.45),
            L_Upperarm=dirs(ad=.85, ar=-.3, la=.1), L_Forearm=dirs(ad=.95, ar=.25, la=-.15), L_Hand=dirs(ad=1, ar=.05, la=-.2),
            R_Upperarm=dirs(ad=.85, ar=-.3, la=.1, lado=LADO_R), R_Forearm=dirs(ad=.95, ar=.25, la=-.15, lado=LADO_R), R_Hand=dirs(ad=1, ar=.05, la=-.2, lado=LADO_R),
            **mano("L", .95), **mano("R", .95))
clave(26, alto, cadera=mov(ad=.12), respira=.6)
empuja = dict(alto, Spine01=dirs(ad=.3, ar=.95), Spine02=dirs(ad=.25, ar=.95), L_Upperarm=dirs(ad=.95, ar=-.05, la=.05), L_Forearm=dirs(ad=1, ar=.05, la=-.1),
              R_Upperarm=dirs(ad=.95, ar=-.05, la=.05, lado=LADO_R), R_Forearm=dirs(ad=1, ar=.05, la=-.1, lado=LADO_R), Mandibula=boca(.2))
clave(36, empuja, cadera=mov(ad=.16), respira=.2); clave(42, empuja, cadera=mov(ad=.16))
suelta = base(Spine01=dirs(ad=.05, ar=1), Head=dirs(ad=.3, ar=.95), Mandibula=boca(.55), **cejas(1),
              L_Upperarm=dirs(ad=.5, ar=-.6, la=.55), L_Forearm=dirs(ad=.6, ar=-.2, la=.6), L_Hand=dirs(ad=.6, ar=0, la=.6),
              R_Upperarm=dirs(ad=.5, ar=-.6, la=.55, lado=LADO_R), R_Forearm=dirs(ad=.6, ar=-.2, la=.6, lado=LADO_R), R_Hand=dirs(ad=.6, ar=0, la=.6, lado=LADO_R),
              **mano("L", 0, abre=.9), **mano("R", 0, abre=.9))
clave(50, suelta, cadera=mov(ad=.14))
clave(62, base(Head=dirs(ad=.06, ar=1), **cejas(.2)), cadera=mov(ad=.12), apoyo=.2)
rellena_cola(62); rellena_suelo(62, levanta_en=[(3, 12, "L"), (13, 21, "R")])

# ---------- Adiós (2,2 s): pulgar arriba con la derecha, saluda con la izquierda, sonrisa grande y pequeña reverencia ----------
accion("Adios", 2.2); COLA.update(amp=.26, f=1.2, pitch=.06, arrastre=0)
clave(0, base(), apoyo=-.2)
def ad(k, habla):
    return base(Spine02=dirs(ad=.06, ar=1), Head=dirs(ad=.15, ar=1, la=-.08 * k, lado=LADO_L), Mandibula=boca(habla), **cejas(1),
                L_Upperarm=dirs(ad=.25, ar=.75, la=.6), L_Forearm=dirs(ad=.15, ar=1, la=.1), L_Hand=dirs(ad=.1, ar=1, la=k),
                R_Upperarm=dirs(ad=.7, ar=-.55, la=.2, lado=LADO_R), R_Forearm=dirs(ad=.9, ar=.35, la=0, lado=LADO_R), R_Hand=dirs(ad=.5, ar=.85, la=0, lado=LADO_R),
                **mano("L", 0, abre=1), **mano("R", .95, pulgar=True))
clave(6, base(**cejas(1), Mandibula=boca(.7), L_Upperarm=dirs(ad=.5, ar=.2, la=.6), R_Upperarm=dirs(ad=.6, ar=-.6, la=.2, lado=LADO_R)), apoyo=-.3)
clave(12, ad(-.35, .8), apoyo=-.4); clave(19, ad(.45, .4), apoyo=-.4); clave(26, ad(-.45, .9), apoyo=-.4); clave(33, ad(.45, .5), apoyo=-.4)
clave(42, base(Spine01=dirs(ad=.35, ar=.9), Spine02=dirs(ad=.3, ar=.9), Head=dirs(ad=.6, ar=.8), Mandibula=boca(.3), **cejas(.4)), apoyo=-.1)
clave(52, base(Head=dirs(ad=.06, ar=1)))
rellena_cola(52); rellena_suelo(52)

# ---------- Teclear (2,4 s): de frente a la pantalla, brazo derecho a la altura del pecho, índice estirado, cuatro toques y mira la taquilla ----------
accion("Teclear", 2.4); COLA.update(amp=.1, f=.8, pitch=.0, arrastre=0)
def tecla(pulsa, mira_pantalla=True):
    return base(Spine01=dirs(ad=.1, ar=1), Spine02=dirs(ad=.1, ar=1), Head=dirs(ad=.3, ar=1) if mira_pantalla else dirs(ad=.5, ar=.85, la=-.25),
                Mandibula=boca(.25), **cejas(.5),
                R_Upperarm=dirs(ad=.9, ar=.05, la=.1, lado=LADO_R), R_Forearm=dirs(ad=1, ar=.18 - .1 * pulsa, la=-.1, lado=LADO_R), R_Hand=dirs(ad=1, ar=.12 - .12 * pulsa, la=-.1, lado=LADO_R),
                **mano("R", indice=True), **mano("L", .2))
clave(0, base(Head=dirs(ad=.6, ar=.8)), apoyo=.2)
clave(8, tecla(0), apoyo=.3)
for i, f in enumerate([13, 21, 29, 37]):
    clave(f, tecla(1), apoyo=.3); clave(f + 4, tecla(0), apoyo=.3)
clave(46, dict(tecla(0, mira_pantalla=False), Mandibula=boca(.6), **cejas(1)), apoyo=.2)   # la taquilla se abre: sorpresa alegre
clave(57, base(Head=dirs(ad=.6, ar=.75), Mandibula=boca(.5)), apoyo=0)
rellena_cola(57); rellena_suelo(57)

# ---------- Cerrar (1,6 s): empuja la puerta con la palma abierta, la acompaña hasta que cierra y asiente ----------
accion("Cerrar", 1.6); COLA.update(amp=.14, f=.9, pitch=.02, arrastre=.1)
def empuje(k):
    """k 0..1: cuánto ha extendido el brazo"""
    return base(Spine01=dirs(ad=.12 + .2 * k, ar=1), Spine02=dirs(ad=.1 + .15 * k, ar=1), Head=dirs(ad=.4, ar=.92), Mandibula=boca(.25),
                R_Upperarm=dirs(ad=.75 + .25 * k, ar=-.2 + .2 * k, la=.15, lado=LADO_R), R_Forearm=dirs(ad=1, ar=.12, la=-.05, lado=LADO_R), R_Hand=dirs(ad=1, ar=.05, la=-.2, lado=LADO_R),
                **mano("R", 0, abre=.4), **mano("L", .2))
clave(0, base(Head=dirs(ad=.6, ar=.8)), apoyo=.2)
clave(8, empuje(.3), apoyo=-.2)
clave(18, empuje(1), cadera=mov(ad=.03), apoyo=-.5)       # la puerta cierra aquí
clave(24, empuje(.9), cadera=mov(ad=.02), apoyo=-.3)
clave(32, base(Head=dirs(ad=.3, ar=.95, la=-.1, lado=LADO_R), Mandibula=boca(.5), **cejas(.8)), apoyo=.1)   # asiente
clave(38, base(Head=dirs(ad=.1, ar=1)), apoyo=0)
rellena_cola(38); rellena_suelo(38)

# ---------- a pistas NLA ----------
arm.animation_data.action = None
for nombre, (ac, frames) in acciones.items():
    ac.frame_range = (0, frames)
    pista = arm.animation_data.nla_tracks.new(); pista.name = nombre
    tira = pista.strips.new(nombre, 0, ac); tira.name = nombre
    if hasattr(ac, "slots") and hasattr(tira, "action_slot"): tira.action_slot = ac.slots[0]
    pista.mute = True
bpy.ops.object.mode_set(mode="OBJECT")

# ---------- previas: cada acción desde tres ángulos ----------
if PREVIAS:
    os.makedirs(PREVIAS, exist_ok=True)
    cam_d = bpy.data.cameras.new("c"); cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam; cam.rotation_mode = "QUATERNION"
    luz_d = bpy.data.lights.new("l", "SUN"); luz_d.energy = 3; luz = bpy.data.objects.new("luz", luz_d); sc.collection.objects.link(luz); luz.rotation_euler = (math.radians(50), 0, math.radians(30))
    sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "TEXTURE"
    sc.render.resolution_x = 300; sc.render.resolution_y = 400
    ANGULOS = {"frente": F * 2.8 + U * .9 + LADO_L * .5, "tres4": F * 2.2 + U * 1.0 + LADO_L * 1.9, "cara": F * 1.1 + U * .95 + LADO_L * .35, "manos": F * 1.2 + U * .5 + LADO_R * .55}
    for nombre, (ac, frames) in acciones.items():
        for p in arm.animation_data.nla_tracks: p.mute = (p.name != nombre)
        for ang, pos in ANGULOS.items():
            cam.location = pos; mira = Vector((hipx, 0, .55)) if ang in ("frente", "tres4") else Vector((hipx + F.x * .15, 0, .85)) if ang == "cara" else Vector((hipx + F.x * .12, -.2 * LADO_L.y, .38))
            cam.rotation_quaternion = (cam.location - mira).to_track_quat("Z", "Y"); cam_d.lens = 50 if ang in ("frente", "tres4") else 70
            for i, f in enumerate([0, int(frames * .3), int(frames * .55), int(frames * .8)]):
                sc.frame_set(f); sc.render.filepath = os.path.join(PREVIAS, f"{nombre}-{ang}-{i}.png"); bpy.ops.render.render(write_still=True)
    for p in arm.animation_data.nla_tracks: p.mute = True
    bpy.data.objects.remove(cam); bpy.data.objects.remove(luz)

# ---------- exportar ----------
for p in arm.animation_data.nla_tracks: p.mute = False
bpy.ops.export_scene.gltf(filepath=DESTINO, export_format="GLB", use_selection=False, use_visible=False, export_animations=True,
                          export_animation_mode="NLA_TRACKS", export_nla_strips=True, export_force_sampling=True, export_frame_step=2,
                          export_image_format="WEBP", export_image_quality=80, export_apply=False, export_yup=True, export_skins=True, export_def_bones=False)
print("EXPORTADO", DESTINO, os.path.getsize(DESTINO) // 1024, "KB", "clips:", list(acciones), "huesos:", len(arm.data.bones))

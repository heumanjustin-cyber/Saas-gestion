"""Monta la película de la portada de Trébol: los cuadros que la página pasa con el scroll.

Fuera (plano fijo de la fachada con acercamiento) → llegada y puerta → pasillo → el sillón del espejo de LED.
Cada tramo se estabiliza por separado (vidstab, suavizado fuerte, zoom fijo), se une con fundidos, se le da el
mismo color a todo y se guarda cuadro a cuadro en WebP (30 por segundo), para que la cámara avance con el dedo
sin saltos. Además deja el último cuadro en alta (peli/sillon.webp) para el gesto de sentarse.

    python web/trebol/herramientas/build_peli.py
"""
import json
import os
import subprocess

from PIL import Image

# Rutas relativas a web/trebol (la carpeta de encima de herramientas/). El vídeo original va en videos/trebol.mp4.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "videos", "trebol.mp4")
OUT = os.path.join(HERE, "peli")
TMP = os.path.join(HERE, "peli_tmp")
os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)
W, H = 1080, 1920
GRADE = "eq=contrast=1.08:saturation=1.1:gamma=0.97,vignette=angle=PI/5"


def run(args):
    subprocess.run(args, check=True)


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True, check=True).stdout.strip())


def tramo(name, a, b, smoothing=30):
    trf = os.path.join(TMP, f"{name}.trf")
    out = os.path.join(TMP, f"{name}.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-to", str(b), "-i", SRC,
         "-vf", f"transpose=1,vidstabdetect=shakiness=8:accuracy=15:stepsize=6:result={trf}", "-f", "null", "-"])
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-to", str(b), "-i", SRC,
         "-vf", f"transpose=1,vidstabtransform=input={trf}:smoothing={smoothing}:optzoom=1:interpol=bicubic:crop=black,"
                f"fps=30,scale={W}:{H}:flags=lanczos,setsar=1,format=yuv420p",
         "-an", "-c:v", "libx264", "-crf", "10", "-preset", "medium", out])
    return out


# 1) Fuera: la fachada (segundo 0.32, en horizontal). Recorrido del letrero a la puerta, acercándose.
fach_png = os.path.join(TMP, "fachada.png")
run(["ffmpeg", "-v", "error", "-y", "-ss", "0.32", "-i", SRC, "-frames:v", "1", fach_png])
img = Image.open(fach_png).convert("RGB")          # 1920x1080
fdir = os.path.join(TMP, "fach")
os.makedirs(fdir, exist_ok=True)
N = 84                                             # 2,8 s a 30 cuadros
for k in range(N):
    u = k / (N - 1)
    e = u * u * (3 - 2 * u)
    cx = 640 + (1215 - 640) * e                    # centro: del letrero a la puerta
    z = 1.0 + 0.16 * e                             # acercamiento suave
    ch = 1080 / z
    cw = ch * 9 / 16
    cy = 540 + 40 * e
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    img.crop(tuple(int(round(v)) for v in box)).resize((W, H), Image.LANCZOS).save(os.path.join(fdir, f"{k:03d}.png"))
F = os.path.join(TMP, "F.mp4")
run(["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-i", os.path.join(fdir, "%03d.png"), "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", F])

# 2) Delante de la puerta: se abre y se ve el interior con el espejo de luz al fondo
A = tramo("D", 5.1, 7.35, smoothing=24)

# 3) El pasillo: acercamiento suave hacia el espejo de luz (cuadro del segundo 10.46, el más nítido)
run(["ffmpeg", "-v", "error", "-y", "-ss", "10.458", "-i", SRC, "-vf", "transpose=1", "-frames:v", "1", os.path.join(TMP, "pasillo.png")])
pas = Image.open(os.path.join(TMP, "pasillo.png")).convert("RGB")   # 1080x1920, ya derecho
edir = os.path.join(TMP, "pas")
os.makedirs(edir, exist_ok=True)
NE = 54
for k in range(NE):
    u = k / (NE - 1)
    e = u * u * (3 - 2 * u)
    z = 1.0 + 0.55 * e
    cw, ch = W / z, H / z
    cx = min(max(W * (0.5 + (0.31 - 0.5) * e), cw / 2), W - cw / 2)
    cy = min(max(H * (0.5 + (0.36 - 0.5) * e), ch / 2), H - ch / 2)
    pas.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W, H), Image.LANCZOS).save(os.path.join(edir, f"{k:03d}.png"))
E = os.path.join(TMP, "E.mp4")
run(["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-i", os.path.join(edir, "%03d.png"), "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", E])

# 4) Dentro: de la pared de las puertas al sillón del espejo de LED
C = tramo("C", 15.3, 17.62, smoothing=20)

dF, dA, dE = dur(F), dur(A), dur(E)
x1, x2, x3 = 0.45, 0.5, 0.55
o1 = dF - x1
o2 = o1 + dA - x2
o3 = o2 + dE - x3

# 5) Los cuadros para el scroll: 600×1066 en WebP (unos 4 MB los 233)
FW, FH = 600, 1066
png = os.path.join(TMP, "cuadros")
os.makedirs(png, exist_ok=True)
for f in os.listdir(png):
    os.remove(os.path.join(png, f))
for f in os.listdir(OUT):
    os.remove(os.path.join(OUT, f))
filt = (f"[0:v][1:v]xfade=transition=fade:duration={x1}:offset={o1:.3f}[a];"
        f"[a][2:v]xfade=transition=fade:duration={x2}:offset={o2:.3f}[b];"
        f"[b][3:v]xfade=transition=fade:duration={x3}:offset={o3:.3f},{GRADE},scale={FW}:{FH}:flags=lanczos[v]")
run(["ffmpeg", "-v", "error", "-y", "-i", F, "-i", A, "-i", E, "-i", C, "-filter_complex", filt, "-map", "[v]",
     os.path.join(png, "%03d.png")])
cuadros = sorted(os.listdir(png))
total = 0
for k, f in enumerate(cuadros):
    dst = os.path.join(OUT, f"{k:03d}.webp")
    Image.open(os.path.join(png, f)).convert("RGB").save(dst, "WEBP", quality=62, method=6)
    total += os.path.getsize(dst)

# 6) El último cuadro en alta, con el mismo color, para el gesto de sentarse
run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.08", "-i", C, "-vf", GRADE, "-frames:v", "1", os.path.join(TMP, "final.png")])
Image.open(os.path.join(TMP, "final.png")).convert("RGB").save(os.path.join(OUT, "sillon.webp"), "WEBP", quality=84, method=6)

# Dónde empieza cada plano, en cuadros (para colocar las frases de la página)
fps = 30
planos = {"fachada": 0, "puerta": round((o1 + x1 / 2) * fps), "pasillo": round((o2 + x2 / 2) * fps), "dentro": round((o3 + x3 / 2) * fps)}
json.dump({"cuadros": len(cuadros), "w": FW, "h": FH, "planos": planos}, open(os.path.join(OUT, "peli.json"), "w"), indent=1)
print(len(cuadros), "cuadros", f"{total / 1048576:.1f} MB", planos)

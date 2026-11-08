"""Monta la película de entrada de Trébol (vídeo que se reproduce solo, como el del reel).

Fuera (plano fijo de la fachada con acercamiento) → llegada y puerta → pasillo → el sillón del espejo de LED.
Cada tramo se estabiliza por separado (vidstab, suavizado fuerte, zoom fijo), se une con fundidos y se le da
el mismo color a todo. Además deja el último cuadro en alta para la animación de «sentarse».
"""
import json
import os
import subprocess

from PIL import Image

# Rutas relativas a web/trebol (la carpeta de encima de herramientas/). El vídeo original va en videos/trebol.mp4.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "videos", "trebol.mp4")
OUT = os.path.join(HERE, "cine")
TMP = os.path.join(HERE, "cine_tmp")
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

dF, dA, dE, dC = dur(F), dur(A), dur(E), dur(C)
x1, x2, x3 = 0.45, 0.5, 0.55
o1 = dF - x1
o2 = o1 + dA - x2
o3 = o2 + dE - x3
filt = (f"[0:v][1:v]xfade=transition=fade:duration={x1}:offset={o1:.3f}[a];"
        f"[a][2:v]xfade=transition=fade:duration={x2}:offset={o2:.3f}[b];"
        f"[b][3:v]xfade=transition=fade:duration={x3}:offset={o3:.3f},{GRADE},"
        f"noise=alls=4:allf=t+u,scale=720:1280:flags=lanczos,format=yuv420p[v]")
cine = os.path.join(OUT, "entrada.mp4")
run(["ffmpeg", "-v", "error", "-y", "-i", F, "-i", A, "-i", E, "-i", C, "-filter_complex", filt, "-map", "[v]", "-an",
     "-c:v", "libx264", "-profile:v", "high", "-crf", "20", "-preset", "slow", "-movflags", "+faststart", cine])
dA = dA + dE - x2   # para los tramos de abajo: puerta + pasillo
x2 = x3

# 4) Póster (primer cuadro) y último cuadro en alta, con el mismo color, para la animación de sentarse
run(["ffmpeg", "-v", "error", "-y", "-i", F, "-vf", f"{GRADE},scale=720:1280:flags=lanczos", "-frames:v", "1", os.path.join(TMP, "poster.png")])
Image.open(os.path.join(TMP, "poster.png")).save(os.path.join(OUT, "poster.webp"), "WEBP", quality=78, method=6)
run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.08", "-i", C, "-vf", GRADE, "-frames:v", "1", os.path.join(TMP, "final.png")])
Image.open(os.path.join(TMP, "final.png")).convert("RGB").save(os.path.join(OUT, "sillon.webp"), "WEBP", quality=84, method=6)

total = dur(cine)
meta = {"duracion": round(total, 3), "tramos": {"fuera": [0, round(dF - x1 / 2, 2)], "puerta": [round(dF - x1 / 2, 2), round(dF + dA - x1 - x2 / 2, 2)],
                                                 "dentro": [round(dF + dA - x1 - x2 / 2, 2), round(total, 2)]}}
json.dump(meta, open(os.path.join(OUT, "cine.json"), "w"), indent=1)
print(json.dumps(meta), f"{os.path.getsize(cine) / 1048576:.1f} MB")

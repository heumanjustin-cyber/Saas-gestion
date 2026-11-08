"""Monta la secuencia de la cinemática de Trébol a partir del vídeo estabilizado.

Tramos (segundos del vídeo original):
  A 2.7–10.7  la fachada, la puerta y la entrada
  B 12.2–13.75 la sala de espera junto al ventanal
  C 15.4–22.4  los puestos: espejos de LED, techo de hexágonos y el carro
Antes de A va un plano de la fachada con el letrero entero (segundo 0.3, en horizontal).
En cada ventana de 4 cuadros se queda el más nítido; entre tramos, un fundido.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

# Rutas relativas a web/trebol (la carpeta de encima de herramientas/)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(HERE, "videos", "trebol.mp4")
STAB = os.path.join(HERE, "stab.mp4")
OFFSET = 2.4                       # stab.mp4 empieza en el segundo 2.4 del original
OUT = os.path.join(HERE, "film")
W, H = 600, 1066
GRADE = "eq=contrast=1.07:saturation=1.12:gamma=0.97,hqdn3d=1.2:1.2:2:2,unsharp=5:5:0.5:5:5:0"
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(HERE, "film_tmp")
os.makedirs(TMP, exist_ok=True)


def run(args):
    subprocess.run(args, check=True)


# 1) tiempos y nitidez de cada cuadro estabilizado
pts = [float(x.strip(",")) for x in subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time", "-of", "csv=p=0", STAB],
    capture_output=True, text=True, check=True).stdout.split() if x.strip(",")]
small = os.path.join(TMP, "small")
os.makedirs(small, exist_ok=True)
if not os.listdir(small):
    run(["ffmpeg", "-v", "error", "-i", STAB, "-vf", "scale=180:320,format=gray", "-fps_mode", "passthrough", os.path.join(small, "%04d.png")])
files = sorted(os.listdir(small))
sharp = []
for f in files:
    a = np.asarray(Image.open(os.path.join(small, f)), dtype=np.float32)[20:-20, 12:-12]   # sin los bordes negros del estabilizado
    lap = -4 * a[1:-1, 1:-1] + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    sharp.append(float(lap.var()))
n = min(len(pts), len(sharp))
src_t = [OFFSET + t for t in pts[:n]]

segments = [("A", 2.7, 10.7), ("B", 12.2, 13.75), ("C", 15.4, 22.4)]
chosen = {}
for name, a, b in segments:
    idx = [i for i in range(n) if a <= src_t[i] < b]
    picks = []
    for k in range(0, len(idx), 4):
        win = idx[k:k + 4]
        picks.append(max(win, key=lambda i: sharp[i]))
    chosen[name] = picks
    print(name, len(idx), "cuadros ->", len(picks))

# 2) extraer los elegidos a tamaño completo, con el color
allidx = sorted(i for p in chosen.values() for i in p)
expr = "+".join(f"eq(n\\,{i})" for i in allidx)
full = os.path.join(TMP, "full")
os.makedirs(full, exist_ok=True)
for f in os.listdir(full):
    os.remove(os.path.join(full, f))
run(["ffmpeg", "-v", "error", "-i", STAB, "-vf", f"select='{expr}',{GRADE},scale={W}:{H}:flags=lanczos", "-fps_mode", "passthrough",
     os.path.join(full, "%04d.png")])
got = sorted(os.listdir(full))
assert len(got) == len(allidx), (len(got), len(allidx))
by_idx = {i: os.path.join(full, got[k]) for k, i in enumerate(allidx)}

# 3) plano de la fachada (segundo 0.3, horizontal): recorte vertical sobre el letrero y el escaparate, con zoom lento
fach = os.path.join(TMP, "fachada.png")
run(["ffmpeg", "-v", "error", "-y", "-ss", "0.32", "-i", VIDEO, "-frames:v", "1", "-vf", GRADE, fach])
img = Image.open(fach).convert("RGB")             # 1920x1080
seq = []
for k in range(10):                               # barrido por la fachada: el letrero y después la puerta
    u = k / 9
    e = u * u * (3 - 2 * u)                       # suave al empezar y al acabar
    x0 = 300 + (1180 - 300) * e
    seq.append(img.crop((int(x0), 0, int(x0) + 607, 1080)).resize((W, H), Image.LANCZOS))


def fade(a_img, b_img, steps):
    return [Image.blend(a_img, b_img, (s + 1) / (steps + 1)) for s in range(steps)]


def frames_of(name):
    return [Image.open(by_idx[i]).convert("RGB") for i in chosen[name]]


A, B, C = frames_of("A"), frames_of("B"), frames_of("C")
seq += fade(seq[-1], A[0], 6) + A
seq += fade(A[-1], B[0], 6) + B
seq += fade(B[-1], C[0], 6) + C

# 4) guardar en WebP; capítulos en proporción de la secuencia
for f in os.listdir(OUT):
    os.remove(os.path.join(OUT, f))
sizes = 0
for k, im in enumerate(seq):
    p = os.path.join(OUT, f"{k:03d}.webp")
    im.save(p, "WEBP", quality=68, method=6)
    sizes += os.path.getsize(p)
total = len(seq)
start_A = 10 + 6
start_B = start_A + len(A) + 6
start_C = start_B + len(B) + 6
meta = {"frames": total, "w": W, "h": H, "chapters": {"fachada": 0, "puerta": start_A, "espera": start_B, "puestos": start_C}}
json.dump(meta, open(os.path.join(OUT, "film.json"), "w"), indent=1)
# primer cuadro pequeño para que la portada salga al instante
seq[0].resize((150, 266), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6)).save(os.path.join(OUT, "poster-xs.webp"), "WEBP", quality=60)
print(json.dumps(meta), f"{sizes / 1048576:.1f} MB")

# Trébol Barber · web de reservas

Barbería en la calle Portillejo, 11 (Logroño). La web entra en el local con una película que se mueve al
hacer scroll, hecha con un vídeo grabado allí el 3 de noviembre de 2026. Después vienen la reserva, las
fotos del local, las opiniones de Google y el horario.

- `src.html`: la página. Es la misma que se publica como Artifact en claude.ai.
- `build.py`: genera `index.html` para cualquier hosting estático (`python web/trebol/build.py`).
- `film/`: los 153 cuadros de la película (WebP 600×1066, 3,4 MB) y `film.json` con los capítulos.
- `fotos/`: ocho fotos del local sacadas del mismo vídeo.
- `herramientas/build_film.py`: monta la película a partir del vídeo.

## Cómo se hizo la película

El vídeo se grabó con el móvil en vertical sin que el teléfono girara la imagen, así que a partir del
segundo 2 los cuadros van tumbados. El script:

1. Gira el vídeo 90° y lo estabiliza con `vidstab` (dos pasadas de ffmpeg).
2. Se queda con tres tramos: la fachada y la entrada (2,7–10,7 s), la sala de espera (12,2–13,75 s) y los
   puestos (15,4–22,4 s). Los giros bruscos de en medio se descartan.
3. De cada cuatro cuadros elige el más nítido (varianza del laplaciano), para quitar el emborronado del
   movimiento.
4. Abre con un barrido por la fachada (segundo 0,3, grabado en horizontal), une los tramos con fundidos,
   corrige el color y guarda los cuadros en WebP.

Para rehacerla hace falta el vídeo original en `videos/trebol.mp4`, que no está en el repositorio
porque pesa 56 MB:

```bash
ffmpeg -ss 2.4 -to 22.6 -i videos/trebol.mp4 -vf "transpose=1,vidstabdetect=shakiness=8:accuracy=15:stepsize=6:result=transforms.trf" -f null -
ffmpeg -ss 2.4 -to 22.6 -i videos/trebol.mp4 -vf "transpose=1,vidstabtransform=input=transforms.trf:smoothing=14:optzoom=2:zoomspeed=0.2:interpol=bicubic:crop=black" -fps_mode passthrough -an -c:v libx264 -crf 12 stab.mp4
python herramientas/build_film.py
```

## La reserva

Funciona entera con el horario real del local: L, M y J de 10 a 14 y de 16 a 20; X y V de 10 a 20;
S de 10 a 14; D cerrado. Las ocupaciones son de ejemplo y no se envía nada: falta conectarla a la
agenda de BUHOSS. Sin carta pública, los precios se confirman en la barbería. Según sus clientes en
Google, un degradado cuesta entre 15 y 20 €.

# Trébol Barber · web de reservas

Barbería en la calle Portillejo, 11 (Logroño). La portada es una película que se reproduce sola, como las
webs de restaurante que entran en el local desde la calle. Se ve la fachada, te acercas, se abre la puerta,
recorres el pasillo y llegas al sillón del espejo de LED. Al sentarte, la cámara se acerca al espejo y su
marco de luz crece hasta convertirse en el panel de reserva. Debajo vienen las fotos del local, las
opiniones de Google y el horario.

- `src.html`: la página. Es la misma que se publica como Artifact en claude.ai.
- `build.py`: genera `index.html` para cualquier hosting estático (`python web/trebol/build.py`).
- `cine/entrada.mp4`: la película (7,8 s, 720×1280, 3,1 MB), con `entrada.webm` (AV1, 0,8 MB) de reserva
  para los navegadores que no reproducen MP4. `poster.webp` es el primer cuadro y `sillon.webp` el último,
  en alta, para la animación de sentarse.
- `fotos/`: ocho fotos del local sacadas del mismo vídeo.
- `herramientas/build_cine.py`: monta la película a partir del vídeo grabado en el local.

## Cómo se hizo la película

El vídeo se grabó el 3 de noviembre de 2026 con el móvil en vertical sin que el teléfono girara la imagen,
así que los cuadros van tumbados. `build_cine.py`:

1. **Fuera:** a partir del segundo 0,3 (en horizontal), un recorrido por la fachada del letrero a la puerta,
   acercándose.
2. **La puerta:** el tramo del segundo 5,1 al 7,35, girado y estabilizado con `vidstab`: la puerta se abre y
   se ve el espejo de luz al fondo.
3. **El pasillo:** un acercamiento suave hacia el espejo sobre el cuadro más nítido del segundo 10,46.
4. **Dentro:** el tramo del 15,3 al 17,62, estabilizado, de la pared de las puertas al sillón del espejo.

Los tramos se unen con fundidos y llevan el mismo color, viñeta y un poco de grano. Se descartaron los
trozos movidos: la pared de ladrillo, el paso por la puerta casi a oscuras y la vuelta por la sala de
espera, que sale en las fotos.

Para rehacerla hace falta el vídeo original en `videos/trebol.mp4`, que no está en el repositorio porque
pesa 56 MB: `python herramientas/build_cine.py`.

## La reserva

Va dentro del espejo, paso a paso: servicio, con quién, día y hora, y tus datos. Usa el horario real del
local: L, M y J de 10 a 14 y de 16 a 20; X y V de 10 a 20; S de 10 a 14; D cerrado. Las horas ocupadas
son de ejemplo y no se envía nada: falta conectarla a la agenda de BUHOSS. Sin carta pública, los
precios se confirman en la barbería. Según sus clientes en Google, un degradado cuesta entre 15 y 20 €.

Con «reducir movimiento» activado, la página abre directamente en el sillón con la reserva, y el
botón «Ver la entrada» pone la película.

# Trébol Barber · web de reservas

Barbería en la calle Portillejo, 11 (Logroño). La portada es una película que avanza con el scroll, como
las webs de cafetería que entran en el local desde la calle: al bajar, la cámara pasa de la fachada a la
puerta, recorre el pasillo y llega al sillón del espejo de LED, con frases grandes encima en cada momento.
Al final te sientas: la cámara se acerca al espejo y su marco de luz crece hasta convertirse en el panel de
reserva. Debajo vienen bloques de color a pantalla completa: la carta, el local, el sillón, las opiniones de
Google, cómo llegar y un pie con el nombre en grande.

- `src.html`: la página. Es la misma que se publica como Artifact en claude.ai.
- `build.py`: genera `index.html` para cualquier hosting estático (`python web/trebol/build.py`).
- `peli/`: la película, en 233 cuadros WebP de 600×1066 (unos 4 MB en total). `sillon.webp` es el último
  cuadro en alta, para el gesto de sentarse. `peli.json` dice en qué cuadro empieza cada plano.
- `fotos/`: ocho fotos del local sacadas del mismo vídeo.
- `herramientas/build_peli.py`: monta la película a partir del vídeo grabado en el local.

## Cómo funciona la portada

La sección mide 8,2 pantallas y deja la imagen fija mientras bajas. La página pinta en un `<canvas>` el
cuadro que toca según lo que llevas bajado, así que la película va hacia delante y hacia atrás con el dedo:

| Bajado | Qué pasa |
| --- | --- |
| 0 – 70 % | Los 233 cuadros: fachada, puerta, pasillo y el giro hasta el sillón, con cinco frases |
| 70 – 84 % | Te sientas: la foto del sillón se acerca al espejo |
| 84 – 93 % | El marco de luz del espejo crece hasta ser el panel de reserva |
| 93 – 100 % | La reserva, quieta, para usarla |

Los cuadros se descargan entrelazados (uno de cada 64, luego de cada 32, 16…), así que la película se puede
recorrer entera desde el primer momento y gana detalle mientras carga. Los botones «Reservar» llevan
directamente al punto de la reserva.

Con «reducir movimiento» activado, la portada es una sola pantalla con la reserva ya abierta.

## Cómo se hizo la película

El vídeo se grabó el 3 de noviembre de 2026 con el móvil en vertical sin que el teléfono girara la imagen,
así que los cuadros van tumbados. `build_peli.py`:

1. **Fuera:** a partir del segundo 0,3 (en horizontal), un recorrido por la fachada del letrero a la puerta,
   acercándose.
2. **La puerta:** el tramo del segundo 5,1 al 7,35, girado y estabilizado con `vidstab`: la puerta se abre y
   se ve el espejo de luz al fondo.
3. **El pasillo:** un acercamiento suave hacia el espejo sobre el cuadro más nítido del segundo 10,46.
4. **Dentro:** el tramo del 15,3 al 17,62, estabilizado, de la pared de las puertas al sillón del espejo.

Los tramos se unen con fundidos, llevan el mismo color y viñeta y se guardan cuadro a cuadro. Se
descartaron los trozos movidos: la pared de ladrillo, el paso por la puerta casi a oscuras y la vuelta por
la sala de espera, que sale en las fotos.

Para rehacerla hace falta el vídeo original en `videos/trebol.mp4`, que no está en el repositorio porque
pesa 56 MB: `python herramientas/build_peli.py`.

## La reserva

Va dentro del espejo, paso a paso: servicio, con quién, día y hora, y tus datos. Usa el horario real del
local: L, M y J de 10 a 14 y de 16 a 20; X y V de 10 a 20; S de 10 a 14; D cerrado. Las horas ocupadas
son de ejemplo y no se envía nada: falta conectarla a la agenda de BUHOSS. Sin carta pública, los
precios se confirman en la barbería. Según sus clientes en Google, un degradado cuesta entre 15 y 20 €.

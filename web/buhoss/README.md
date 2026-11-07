# Web de BUHOSS

Página para enseñar a cualquier negocio qué se le puede montar: peluquería, barbería, restaurante,
bar, kebab, clínica, tienda, reformas, academia o empresa.

- `src.html`: la página. Es la misma que se publica como Artifact en claude.ai, sin `<html>` ni `<head>`.
- `build.py`: genera `index.html` para cualquier hosting estático, con metadatos y fuentes locales
  (sin Google Fonts: ninguna petición a terceros).
- `fonts/`: Bricolage Grotesque, Atkinson Hyperlegible e IBM Plex Mono (licencia SIL OFL 1.1).

## Cambiar algo

1. Edita `src.html`. El número de WhatsApp está al principio del script: `const WHATSAPP = "34…";`.
   Mientras esté vacío, la web no enseña ningún contacto: es para usarla en persona.
2. Genera la versión desplegable: `python web/buhoss/build.py`.

## Publicarla en tu dominio

Sube `index.html` y la carpeta `fonts/` a cualquier hosting estático: GitHub Pages, Netlify,
Cloudflare Pages o el mismo servidor del backend.

## Cómo usarla en una visita

La web es una guía de 8 pasos: 1 Tu negocio · 2 Cómo se ve · 3 Las piezas · 4 Tus números ·
5 Para empresas · 6 Cómo empezamos · 7 Preguntas · 8 Hablemos.

- Pulsa «Empezar la guía, paso a paso»: se ve un paso cada vez, con «Siguiente» y «‹» en la barra de
  abajo (o las flechas del teclado). «Salir» vuelve a la página entera.
- Para saltar a cualquier paso: el botón «Índice» (arriba en móvil y tablet, y en la barra de abajo)
  o la fila de pasos de la cabecera en pantallas grandes. Cada paso acaba con botones al anterior y al
  siguiente.
- Paso 1: elige el tipo de negocio; el resto de la guía cambia con él. Para entrar con uno ya elegido,
  añade a la dirección `#peluqueria`, `#barberia`, `#restaurante`, `#bar`, `#kebab`, `#clinica`,
  `#tienda`, `#reformas`, `#academia` o `#empresa`.
- Paso 2: deja que el dueño toque el móvil de ejemplo («Tu cliente»: reservar una cita, pedir un plato…)
  y enséñale la pantalla de su equipo y el resumen que le llegaría a él.
- Paso 3: marca las piezas que le encajan o pulsa «Añadirlas todas» para las recomendadas. En el
  paso 8 tienes la propuesta escrita, lista para copiar y mandar por WhatsApp.
- Al pasar a otro local: Índice → «Empezar de cero» borra las piezas marcadas y el formulario. Todo
  se guarda solo en tu navegador.

## Lo que se mueve solo

- Portada: en el móvil del dueño pasa la noche (llegan los avisos, amanece y el búho se duerme).
- Paso 2: la demo del cliente se usa sola con un dedo virtual; si alguien toca la pantalla, se para y
  sigue a mano («Verla sola» la vuelve a poner). La pantalla del equipo se mueve en directo: pedidos que
  pasan de columna, citas que se llenan, mesas que piden, stock que baja.
- Las cifras cuentan hasta su valor, los tickets de Verifactu se encadenan y las secciones aparecen al
  bajar.
- «Pausar animaciones», debajo del móvil de la portada, lo para todo. Con «reducir movimiento» activado
  en el móvil o el ordenador, la web sale quieta.

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

- Abre la web en el móvil o la tablet y elige el tipo de negocio. Para ir directo a uno, usa su
  dirección con `#peluqueria`, `#barberia`, `#restaurante`, `#bar`, `#kebab`, `#clinica`, `#tienda`,
  `#reformas`, `#academia` o `#empresa` al final.
- Deja que el dueño toque la demo del móvil: reserva una cita o pide un plato como lo haría su cliente.
- Mueve la calculadora con sus números.
- Marca en «Lo que se monta» las piezas que le encajan. Con «Propuesta» las copias en un texto listo
  para mandárselo por WhatsApp. Las piezas marcadas se guardan solo en tu navegador.

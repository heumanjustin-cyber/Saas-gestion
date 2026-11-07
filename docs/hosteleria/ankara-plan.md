# Ankara Kebab: dejar obsoleto el QR de Studio 42 e instalar BUHOS con TPV

Auditoría hecha el 7-11-2026 sobre lo que hay publicado hoy:
`https://studio42.es/c/?cod=ankara-kebab` (el QR), `https://studio42.es/ankara/` (carta y pedidos) y
`https://studio42.es/ankara/cocina/` (pantalla de cocina).

## 1. Qué tiene hoy Ankara

- **El QR** abre una página de Studio 42 alojada en GitHub Pages. Esa página carga
  `ankara-kebab.json` y pinta sus botones: «Ver la carta y pedir», alérgenos, «¿Encontraste estas
  llaves?», «¿Dónde aparqué?», guardar contacto y opinión (Google o WhatsApp).
- **La carta con pedidos** tiene 42 platos y permite pedir a la mesa, para recoger o a domicilio
  (1 €, mínimo 10 €). Pagas al recoger, en efectivo, tarjeta o Bizum. El pedido va a un Google
  Apps Script y, si falla, sale por WhatsApp.
- **La cocina** es una página que consulta ese Apps Script cada pocos segundos.
- **Precio de Studio 42:** pack Arranque 99 € + IVA o Referente 349 € + IVA, más una cuota de
  19 €/mes (Esencial) o 39 €/mes (Pro). No incluye TPV.

## 2. Fallos encontrados

| # | Fallo | Por qué importa | En BUHOS |
|---|---|---|---|
| 1 | Los pedidos van a un Google Apps Script. Su propio código dice que falta crear la clave de Ankara: hasta entonces el cliente ve «No pudimos enviarlo directo» y lo manda por WhatsApp | Los pedidos pueden no llegar a cocina | El pedido se guarda en la base de datos de BUHOS y la cocina lo ve al momento (medido: 1,5 s) |
| 2 | El precio lo calcula el móvil y nadie lo comprueba | Cualquiera puede mandar un pedido con precios inventados | El precio lo calcula el servidor desde la carta |
| 3 | El código de pedido es aleatorio de 4 cifras (AK-1234) | Con 100 pedidos al día hay un 42 % de probabilidad de que dos clientes tengan el mismo código | Número correlativo del día: 001, 002… |
| 4 | La mesa va en la URL (`?mesa=4`) | Cualquiera la cambia y pide «a la mesa 2» desde casa | Cada mesa tiene un QR propio, y se puede cambiar si alguien se lleva una foto |
| 5 | Alérgenos: 4 tarjetas genéricas, y una es «picante», que no es alérgeno. Su código lo reconoce: «pendiente de confirmar con el dueño plato a plato» | El RD 126/2015 exige informar de los 14 alérgenos por plato | 14 alérgenos por plato y por opción (la salsa blanca lleva lácteos, el falafel gluten). El cliente puede filtrar, y un plato sin confirmar nunca sale como seguro |
| 6 | Datos duplicados y contradictorios: el QR dice que el domingo abre a las 09:00 y la web, a las 13:30 (lo confirmó el dueño el 30/10) | El cliente ve horarios distintos según por dónde entre | Una sola ficha. Horario con tramos de madrugada (martes hasta la 1:30) |
| 7 | La web de pedidos está en borrador con `noindex`. El QR es una página que, sin JavaScript, solo enseña «Cargando…» con el título «Studio 42 · Terminal Phygital» | Google no ve a Ankara | La página sale ya montada desde el servidor, con el nombre del local, la carta en el HTML y datos estructurados de Restaurant y Menu |
| 8 | No hay TPV: el pedido no genera ticket | En la caja se vuelve a teclear (doble trabajo, errores, descuadres) | Un toque en el TPV convierte el pedido del QR en ticket |
| 9 | Sin Verifactu | Obligatorio desde el 1-7-2027 para autónomos y el 1-1-2027 para sociedades (RDL 15/2025) | Tickets y facturas encadenados con huella SHA-256 y QR tributario (ver §6) |
| 10 | Solo en español | Logroño está en el Camino de Santiago | Español, inglés y francés, según el idioma del móvil |
| 11 | El QR y el NFC apuntan a `studio42.es`. Si se deja de pagar, la página se pone «en pausa» | Ankara depende del proveedor | QR dinámicos que se pueden cambiar sin reimprimir. Opción de usar un dominio propio |
| 12 | Usa Google Fonts y otros recursos de terceros | Más peso y riesgo RGPD (en la UE ya hay sentencias contra Google Fonts por enviar la IP del visitante) | Ninguna petición a terceros. 15,5 KB comprimido |
| 13 | El seguimiento del pedido consulta cada 12 s | Avisa tarde | En vivo |

Lo que no se ha copiado: «¿Encontraste estas llaves?» y «¿Dónde aparqué?». Solo tienen sentido en el
llavero NFC de Studio 42. Si Ankara los usa, se añaden en una tarde.

## 3. Qué hace ya BUHOS (en este repositorio)

- **Página del local** en `/r/ankara-kebab`, con la carta real de Ankara ya cargada (42 platos,
  grupos de elección, extras, «sin cebolla», «¿Lo hacemos menú?» que conserva la carne y la salsa
  elegidas, y «¿Algo de beber?» solo donde el menú no lleva bebida).
- **Pedido** a la mesa (solo con el QR de la mesa), para recoger o a domicilio, con hora programada
  cuando el local está cerrado. Pausa automática cuando la cocina va a tope y agotados en un toque.
- **Seguimiento en vivo** del pedido: Recibido → En la cocina → ¡Listo! → Entregado. Vibra al estar
  listo y el enlace sigue valiendo si se cierra la página.
- **Cocina** en `/app/cocina`: columnas Nuevos / En cocina / Listos, tiempo de espera en colores,
  aviso sonoro, rechazo con motivo, comanda impresa, pausar pedidos y agotados.
- **TPV** en `/app/tpv`:
  - Se empareja con un código; cada empleado entra con su PIN.
  - Tickets con opciones y cobro en efectivo (con cambio), tarjeta, Bizum o mixto.
  - Cobra los pedidos del QR de una mesa juntos.
  - Devoluciones (R5), anulación, factura con NIF (F3), entradas y salidas de caja e informes X y Z
    con arqueo por billetes y monedas.
- **QR dinámicos** por pieza (mesa, display, puerta, llavero, bolsa), con escaneos, pedidos y ventas
  por pieza. Hoja A4 de pegatinas lista para imprimir.
- **Opiniones:** dos botones con el mismo peso, como piden las normas de Google: reseña en Google o
  comentario privado al dueño (queda guardado, sin depender de WhatsApp).
- **Migración** desde Studio 42 en un comando (`scripts/import_studio42.py`). Sirve para cualquier
  cliente suyo, no solo para Ankara.

## 4. Plan para Ankara

**Demo (20 min, en el local):**
1. El dueño escanea un QR de mesa con su móvil y ve su carta en BUHOS.
2. Pide un dürüm.
3. El pedido suena en la tablet de cocina.
4. Se cobra en el TPV en un toque y sale el ticket.

**Instalación (1 día):**
1. Datos fiscales (NIF y razón social). ¿Ankara es SL o autónomo? Eso decide su plazo de Verifactu.
2. Repasar con el dueño los 14 alérgenos plato a plato (unos 30 min). Hoy están precargados desde
   su tarjeta genérica y marcados «sin confirmar».
3. Montar la impresora térmica, el cajón y la tablet de cocina, y poner Chrome en modo quiosco para
   imprimir sin diálogo.
4. Emparejar el TPV y la cocina, y crear el PIN de cada empleado.
5. Imprimir y pegar los QR: 4 mesas, display de barra, vinilo de la puerta, llaveros y bolsa de
   reparto. Quitar las pegatinas de Studio 42.
6. Tickets de prueba en modo pruebas y, después, pasar a producción.
7. Formación: 30 min con barra y 15 min con cocina.

**Primera semana:** ajustar el tiempo de preparación y revisar qué pieza trae más pedidos (analítica
por QR).

## 5. Oferta «BUHOS con TPV» (propuesta: ajusta los números)

Referencias de mercado (blogs y comparativas, sin confirmar con cada proveedor):

| Producto | Precio |
|---|---|
| Glop | desde 19,90 €/mes |
| Ágora | 34, 62 o 90 €/mes |
| Cegid Revo | unos 30 €/mes |
| Tipsi (con hardware) | desde 33,95 €/mes |
| TPV en la nube, en general | 25 a 150 €/mes |
| Studio 42 (sin TPV) | 19 a 39 €/mes |
| Impresora Epson TM-m30III | 265 a 325 € |

| Pack | Incluye | Alta | Cuota |
|---|---|---|---|
| Carta QR | Carta multidioma, pedidos (mesa, recoger, domicilio), cocina en pantalla, QR por pieza con estadísticas, opiniones | Gratis si viene de Studio 42; 99 € si no | 19 €/mes |
| TPV completo | Todo lo anterior + TPV, caja y cierres, devoluciones y facturas, Verifactu | 199 € (instalación, carta, alérgenos, PIN y formación) | 39 €/mes con 1 caja; +15 €/mes por caja extra |
| Hardware | Impresora térmica, cajón y tablet de cocina. Funciona en cualquier navegador: vale la tablet que ya tengan | A precio de distribuidor + montaje, o en renting | — |

**Argumento de venta:** por lo mismo que la cuota Pro de Studio 42, Ankara tiene además TPV, cocina,
cierres de caja y Verifactu. Y no hay que comprar hardware de una marca concreta.

## 6. Lo que todavía falta (dicho claro)

1. **Seguridad del SaaS que ya existía (urgente, antes de instalar en un cliente real).**
   - Estas rutas no piden autenticación y devuelven datos de **todas** las empresas: `GET /clients`,
     `/companies`, `/employees`, `/services`, `/appointments`, `/locations`, `/resources`,
     `/dashboard`, `/permissions`, `/roles` y `/memberships`.
   - Estas otras borran sin sesión: `DELETE /clients/{id}`, `/employees/{id}`, `/services/{id}` y
     `/appointments/{id}`.
   - Las contraseñas se guardan con SHA-256 sin sal: hay que pasar a bcrypt o argon2 y rehashear al
     iniciar sesión.
   - Los módulos nuevos de hostelería no tienen este problema.
2. **Envío a la AEAT.**
   - Ya funcionan la huella, la cadena, el QR y el XML.
   - Falta validar el XML contra el XSD en el entorno de pruebas, el envío con el certificado del
     titular y la declaración responsable de BUHOS como productor del software.
3. **Modo sin conexión del TPV.** Hoy, si cae internet, no se cobra. Mientras tanto: router 4G de
   respaldo. Siguiente paso: cola local de tickets.
4. **Pago online** (tarjeta o Bizum) para domicilio, para evitar pedidos falsos.
5. **Panel web del dueño** para editar la carta. Hoy se hace por API o con el importador. Agotados,
   oferta del día y pausa ya se gestionan desde el TPV y la cocina.
6. **Integraciones:** datáfono (hoy se confirma a mano), Glovo, Uber Eats y Just Eat.
7. **Fotos de los platos.**

## 7. Fuentes

- Plazos de Verifactu (RDL 15/2025):
  [ICAM](https://web.icam.es/se-retrasa-al-2027-la-entrada-en-vigor-de-verifactu-la-nueva-normativa-de-facturacion-electronica/),
  [SuperContable](https://www.supercontable.com/boletin/G/articulos/aplazado_verifactu_hasta_2027_como_actuar_seguir_cambio_obligacion_programas_facturacion.html)
- Huella SHA-256 de los registros:
  [verifactu-demo (reproduce los ejemplos de la AEAT)](https://github.com/alejandrocorral509/verifactu-demo),
  [DEV Community](https://dev.to/a_molina_b9d7a17c33863229/implementando-la-huella-sha-256-de-verifactu-6-detalles-que-rompen-el-hash-y-uno-que-rompe-la-1d82).
  Comprobado aquí con los tres ejemplos oficiales (`tests/test_verifactu.py`).
- QR tributario (URL de cotejo, 30 a 40 mm, nivel M):
  [Quaderno](https://quaderno.io/es/articulos/facturacion-electronica/codigo-qr-factura/),
  [verifactu.co](https://verifactu.co/qr-verifactu/)
- Factura simplificada hasta 3.000 € en hostelería:
  [AEAT, manual de IVA](https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-iva-2026/capitulo-10-obligac-formales-suj-registro/obligaciones-materia-facturacion/facturas-simplificadas.html),
  [Qamarero](https://qamarero.com/blog/que-es-una-factura-simplificada-en-un-restaurante/)
- IVA de refrescos para llevar (por eso existe `takeaway_tax_rate`; que lo decida la gestoría):
  [Qamarero, IVA en restaurantes](https://qamarero.com/blog/iva-restaurantes/),
  [Alimarket](https://www.alimarket.es/alimentacion/noticia_amp/322475/el-gobierno-eleva-al-21--el-iva-de-bebidas-azucaradas-y-edulcoradas--salvo-en-hosteleria)
- Precios de TPV:
  [etersystem](https://etersystem.es/blog/tpv-hosteleria-restaurante-mejores-opciones-2026),
  [ingenieriademenu](https://ingenieriademenu.com/software-tpv-hosteleria/),
  [vantaris](https://vantaris.es/blog/cuanto-cuesta-un-tpv)
- Impresora Epson TM-m30III:
  [PcBox](https://www.pcbox.com/c31ck50112-impresora-termica-epson-tm-m30iii/p),
  [Comercialtpv](https://www.comercialtpv.com/en/epson-c31ck50111.html)

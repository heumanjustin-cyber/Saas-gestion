# BUHOS OS · Backend

API de gestión (FastAPI + PostgreSQL) con el módulo de **hostelería**: carta QR con pedidos, cocina en
pantalla, TPV con Verifactu y migración desde Studio 42.

## Arrancar en local

```bash
cd Backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/buhos
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
export ALGORITHM=HS256
export PUBLIC_BASE_URL=https://tu-dominio.es   # la URL que llevan impresa los QR

python -m app.db.init_db                         # crea solo las tablas que falten
python -m scripts.seed_ankara --email dueno@ankara.es --password 'una-clave-larga'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`init_db` usa `create_all`: añade las tablas nuevas sin tocar las existentes. Los triggers de
inalterabilidad fiscal se crean junto con sus tablas.

| Pantalla | URL | Quién |
|---|---|---|
| Carta y pedidos del local | `/r/<slug>` (p. ej. `/r/ankara-kebab`) | Cliente (móvil) |
| Destino de cada QR impreso | `/q/<código>` → redirige y cuenta el escaneo | Cliente |
| TPV | `/app/tpv` | Barra (tablet o TPV táctil) |
| Cocina | `/app/cocina` | Cocina (tablet en la pared) |
| Hoja de QR para imprimir | `GET /my/venues/<company_id>/qr-sheet` | Dueño |
| Documentación de la API | `/docs` | Desarrollo |

## Pruebas

Contra un Postgres real (triggers y contadores atómicos son de Postgres). El esquema de la base de
pruebas se borra y se recrea en cada ejecución.

```bash
createdb buhos_test
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/buhos_test pytest
```

`tests/test_verifactu.py` comprueba la huella con los tres ejemplos oficiales de la AEAT.

## Módulo de hostelería

```
app/models/   venue · menu · dining (mesas y QR) · order · pos (cajas, tickets, pagos) · fiscal
app/services/ hours · allergens · menu_service · order_service · invoice_service · cash_service
              verifactu · nif · qr_service · counters · i18n · ratelimit · studio42_import
app/api/      public_venue · venue_admin · menu_admin · orders_admin · pos · web_apps
app/web/      plantillas Jinja2 (página pública, ticket 80 mm, comanda, informe Z, hoja de QR) y JS sin compilar
scripts/      seed_ankara · import_studio42
seed/ankara/  carta (42 platos), ficha, alérgenos orientativos y traducciones EN/FR
```

**Acceso.** Las rutas `/my/venues/{company_id}/…` aceptan el token del dueño (o de un miembro con
permiso) y el token de un TPV de esa empresa. Un TPV obtiene su token emparejándose con un código de un
solo uso (15 min) y después cada empleado entra con su PIN (bloqueo tras 5 fallos). Una tablet perdida
se desvincula desde `DELETE /my/venues/{id}/pos/devices/{device_id}`.

**Pedidos.** El precio lo calcula siempre el servidor desde la carta. El número del día es correlativo
(001, 002…) con un contador atómico. Un reintento con la misma `client_ref` devuelve el mismo pedido.
Se validan horario (con tramos que cruzan la medianoche), pausas, mínimos de domicilio, opciones
obligatorias, agotados y la mesa (solo con el QR de esa mesa). Cocina y cliente reciben los cambios en
vivo por SSE.

**TPV y Verifactu.** Cada ticket (F2), factura completa (F3), devolución (R5) o anulación genera un
registro encadenado con huella SHA-256 (RD 1007/2023, Orden HAC/1177/2024). Numeración correlativa por
serie y año sin huecos. Postgres impide borrar o cambiar facturas, líneas, pagos y registros. Un NIF
solo puede facturar en una empresa de BUHOS (si no, saldrían dos `T1-2026-000001`).

Hecho: huella (validada con los ejemplos de la AEAT), cadena y su verificación
(`GET /my/venues/{id}/pos/fiscal-records/verify`), QR tributario en el ticket y XML de alta/anulación.

Pendiente antes de emitir en producción con Verifactu:
1. Validar el XML contra el XSD oficial en el entorno de pruebas de la AEAT.
2. Envío SOAP con el certificado electrónico del titular (mTLS) y gestión de respuestas y reintentos.
3. Declaración responsable de BUHOS como productor del software y variables `BUHOS_SIF_*` rellenas.

Plazos (RDL 15/2025): sociedades desde el 1-1-2027; autónomos y resto desde el 1-7-2027.

## Impresión

Ticket y comanda salen en HTML de 80 mm desde el navegador del TPV. Para imprimir sin diálogo, abre
Chrome en modo quiosco: `chrome --kiosk --kiosk-printing https://tu-dominio.es/app/tpv`. El cajón se
abre con la propia impresora (opción «abrir cajón» del controlador de Epson/Star).

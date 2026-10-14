"""
Auditoria de la cuenta de Meta / WhatsApp Cloud API.

Comprueba que esta configurado y que falta para reservar por WhatsApp Flows:
token, portfolio y verificacion, cuentas de WhatsApp (WABA), numeros,
webhooks, plantillas, flows y clave de cifrado.

Uso (solo libreria estandar, Python 3.10+):

    python meta_whatsapp_audit.py --token EAAG... [--waba-id 123] [--app-id 123 --app-secret abc]

- --token: token de acceso (WhatsApp > Configuracion de la API en developers.facebook.com,
  o el token permanente de un usuario del sistema).
- --waba-id: opcional, por si el token no puede listar tus portfolios.
- --app-id / --app-secret: opcionales; permiten ver caducidad y permisos del token
  y la URL de webhook configurada en la app.

El informe no imprime el token ni el app secret.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v23.0"

PHONE_FIELDS = ",".join([
    "display_phone_number",
    "verified_name",
    "name_status",
    "code_verification_status",
    "quality_rating",
    "messaging_limit_tier",
    "platform_type",
    "status",
    "account_mode",
    "is_official_business_account",
])


def get(path, token, **params):
    params["access_token"] = token
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("error", {})
            return None, f"{err.get('code')}: {err.get('message')}"
        except Exception:
            return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, str(e.reason)


def ok(msg):
    print(f"  [OK]   {msg}")


def warn(msg):
    print(f"  [!!]   {msg}")


def info(msg):
    print(f"         {msg}")


def check_token(token, app_id, app_secret):
    print("\n== 1. Token ==")
    me, err = get("me", token, fields="id,name")
    if err:
        warn(f"El token no funciona: {err}")
        sys.exit(1)
    ok(f"Token valido para: {me.get('name')} ({me.get('id')})")

    if not (app_id and app_secret):
        info("Sin --app-id/--app-secret: no compruebo caducidad ni permisos.")
        return
    data, err = get("debug_token", f"{app_id}|{app_secret}", input_token=token)
    if err:
        warn(f"debug_token fallo: {err}")
        return
    d = data.get("data", {})
    info(f"Tipo: {d.get('type')} | App: {d.get('application')}")
    expires = d.get("expires_at", 0)
    if expires == 0:
        ok("No caduca (token permanente)")
    else:
        warn("Caduca (token temporal): para produccion hace falta un token de usuario del sistema")
    scopes = d.get("scopes", [])
    for needed in ("whatsapp_business_messaging", "whatsapp_business_management"):
        (ok if needed in scopes else warn)(f"Permiso {needed}")


def check_app(app_id, app_secret):
    print("\n== 2. App y webhook ==")
    if not (app_id and app_secret):
        info("Sin --app-id/--app-secret: me salto esta parte.")
        return
    app_token = f"{app_id}|{app_secret}"
    app, err = get(app_id, app_token, fields="name")
    if err:
        warn(f"No puedo leer la app: {err}")
        return
    ok(f"App: {app.get('name')}")
    subs, err = get(f"{app_id}/subscriptions", app_token)
    if err:
        warn(f"No puedo leer webhooks: {err}")
        return
    wa = [s for s in subs.get("data", []) if s.get("object") == "whatsapp_business_account"]
    if not wa:
        warn("No hay webhook de WhatsApp configurado en la app")
    for s in wa:
        ok(f"Webhook -> {s.get('callback_url')} (activo={s.get('active')})")
        info("Campos: " + ", ".join(f["name"] for f in s.get("fields", [])))


def find_wabas(token, waba_id):
    print("\n== 3. Portfolio y verificacion del negocio ==")
    wabas = {}
    businesses, err = get("me/businesses", token, fields="id,name,verification_status")
    if err:
        warn(f"No puedo listar portfolios con este token: {err}")
    for b in (businesses or {}).get("data", []):
        status = b.get("verification_status")
        (ok if status == "verified" else warn)(
            f"Portfolio '{b.get('name')}' ({b.get('id')}) verificacion: {status}"
        )
        for edge in ("owned_whatsapp_business_accounts", "client_whatsapp_business_accounts"):
            data, err = get(f"{b['id']}/{edge}", token, fields="id,name")
            for w in (data or {}).get("data", []):
                wabas[w["id"]] = w.get("name")
    if waba_id:
        wabas.setdefault(waba_id, "(pasada por --waba-id)")
    if not wabas:
        warn("No encuentro ninguna cuenta de WhatsApp (WABA). Prueba con --waba-id")
    return wabas


def check_waba(token, waba_id, name):
    print(f"\n== 4. Cuenta de WhatsApp '{name}' ({waba_id}) ==")

    phones, err = get(f"{waba_id}/phone_numbers", token, fields=PHONE_FIELDS)
    if err:
        warn(f"No puedo leer numeros: {err}")
        return
    for p in phones.get("data", []):
        print(f"\n  Numero {p.get('display_phone_number')} - '{p.get('verified_name')}'")
        (ok if p.get("status") == "CONNECTED" else warn)(f"Estado: {p.get('status')}")
        (ok if p.get("name_status") == "APPROVED" else warn)(f"Nombre visible: {p.get('name_status')}")
        info(f"Plataforma: {p.get('platform_type')} | Modo: {p.get('account_mode')}")
        info(f"Calidad: {p.get('quality_rating')} | Limite: {p.get('messaging_limit_tier')}")
        enc, err = get(f"{p['id']}/whatsapp_business_encryption", token)
        if err:
            warn(f"Clave de cifrado para Flows: no se pudo leer ({err})")
        else:
            d = (enc.get("data") or [{}])[0]
            status = d.get("business_public_key_signature_status")
            (ok if status == "VALID" else warn)(f"Clave de cifrado para Flows: {status or 'no subida'}")

    subs, err = get(f"{waba_id}/subscribed_apps", token)
    apps = [a.get("whatsapp_business_api_data", {}).get("name") for a in (subs or {}).get("data", [])]
    (ok if apps else warn)(f"Apps suscritas a esta cuenta (reciben mensajes): {apps or 'ninguna'}")

    tpl, err = get(f"{waba_id}/message_templates", token, fields="name,status,category,language", limit=50)
    items = (tpl or {}).get("data", [])
    info(f"Plantillas: {len(items)}")
    for t in items:
        info(f"  - {t['name']} [{t.get('category')}/{t.get('language')}] {t.get('status')}")

    flows, err = get(f"{waba_id}/flows", token, fields="id,name,status")
    items = (flows or {}).get("data", [])
    info(f"Flows: {len(items)}" + (f" (error: {err})" if err else ""))
    for f in items:
        info(f"  - {f['name']} {f.get('status')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--token", required=True)
    parser.add_argument("--waba-id")
    parser.add_argument("--app-id")
    parser.add_argument("--app-secret")
    args = parser.parse_args()

    check_token(args.token, args.app_id, args.app_secret)
    check_app(args.app_id, args.app_secret)
    for waba_id, name in find_wabas(args.token, args.waba_id).items():
        check_waba(args.token, waba_id, name)
    print("\nListo. Puedes pegar este informe en el chat (no contiene el token).")


if __name__ == "__main__":
    main()

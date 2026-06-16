content = open("app/api/appointment.py").read()
old = '''"client_id": str(a.client_id),
                "service_id": str(a.service_id),'''
new = '''"client_id": str(a.client_id) if a.client_id else None,
                "service_id": str(a.service_id) if a.service_id else None,'''
if old in content:
    open("app/api/appointment.py", "w").write(content.replace(old, new))
    print("Fix aplicado OK")
else:
    print("TEXTO NO ENCONTRADO")

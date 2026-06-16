content = open("app/services/appointment_service.py").read()

old = """def check_schedule(
    db: Session,
    employee_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> bool:
    weekday = starts_at.weekday()
    slot_start = starts_at.time()
    slot_end = ends_at.time()
    return db.query(EmployeeSchedule).filter(
        EmployeeSchedule.employee_id == employee_id,
        EmployeeSchedule.weekday == weekday,
        EmployeeSchedule.start_time <= slot_start,
        EmployeeSchedule.end_time >= slot_end,
    ).first() is not None"""

new = """def check_schedule(
    db: Session,
    employee_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> bool:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Madrid")
    local_start = starts_at.astimezone(tz)
    local_end = ends_at.astimezone(tz)
    weekday = local_start.weekday()
    slot_start = local_start.time().replace(tzinfo=None)
    slot_end = local_end.time().replace(tzinfo=None)
    return db.query(EmployeeSchedule).filter(
        EmployeeSchedule.employee_id == employee_id,
        EmployeeSchedule.weekday == weekday,
        EmployeeSchedule.start_time <= slot_start,
        EmployeeSchedule.end_time >= slot_end,
    ).first() is not None"""

if old in content:
    open("app/services/appointment_service.py", "w").write(content.replace(old, new))
    print("Fix aplicado OK")
else:
    print("TEXTO NO ENCONTRADO - revisar manualmente")

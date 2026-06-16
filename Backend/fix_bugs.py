# Fix 1: employee_schedule.py
content = open("app/api/employee_schedule.py").read()
content = content.replace(
    "employee_id=UUID(schedule.employee_id),",
    "employee_id=schedule.employee_id,"
)
open("app/api/employee_schedule.py", "w").write(content)

# Fix 2: blocked_time.py
bt = open("app/api/blocked_time.py").read()
bt = bt.replace(
    "from datetime import datetime\n",
    ""
).replace(
    "employee_id=UUID(\n            blocked_time.employee_id\n        ),",
    "employee_id=blocked_time.employee_id,"
).replace(
    "starts_at=datetime.fromisoformat(\n            blocked_time.starts_at\n        ),",
    "starts_at=blocked_time.starts_at,"
).replace(
    "ends_at=datetime.fromisoformat(\n            blocked_time.ends_at\n        ),",
    "ends_at=blocked_time.ends_at,"
)
open("app/api/blocked_time.py", "w").write(bt)

# Fix 3: models/user.py - añadir is_verified
user = open("app/models/user.py").read()
user = user.replace(
    "    is_active: Mapped[bool] = mapped_column(\n        Boolean,\n        nullable=False,\n        default=True,\n    )",
    "    is_active: Mapped[bool] = mapped_column(\n        Boolean,\n        nullable=False,\n        default=True,\n    )\n\n    is_verified: Mapped[bool] = mapped_column(\n        Boolean,\n        nullable=False,\n        default=True,\n    )"
)
open("app/models/user.py", "w").write(user)

print("Fixes aplicados OK")

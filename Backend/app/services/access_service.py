from uuid import UUID

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User

from app.models.role import Role
from app.models.permission import Permission
from app.models.membership import CompanyMembership


DEFAULT_PERMISSIONS = [
    ("company.view", "Ver empresa"),
    ("company.edit", "Editar empresa"),
    ("employees.view", "Ver empleados"),
    ("employees.create", "Crear empleados"),
    ("employees.edit", "Editar empleados"),
    ("employees.delete", "Eliminar empleados"),
    ("clients.view", "Ver clientes"),
    ("clients.create", "Crear clientes"),
    ("clients.edit", "Editar clientes"),
    ("clients.delete", "Eliminar clientes"),
    ("services.view", "Ver servicios"),
    ("services.create", "Crear servicios"),
    ("services.edit", "Editar servicios"),
    ("services.delete", "Eliminar servicios"),
    ("appointments.view", "Ver citas"),
    ("appointments.create", "Crear citas"),
    ("appointments.edit", "Editar citas"),
    ("appointments.delete", "Eliminar citas"),
    ("analytics.view", "Ver estadísticas"),
    ("billing.view", "Ver facturación"),
    ("billing.manage", "Gestionar facturación"),
]


DEFAULT_ROLES = {
    "OWNER": [
        p[0] for p in DEFAULT_PERMISSIONS
    ],
    "ADMIN": [
        p[0] for p in DEFAULT_PERMISSIONS
        if p[0] != "billing.manage"
    ],
    "MANAGER": [
        "company.view",
        "employees.view",
        "employees.create",
        "employees.edit",
        "clients.view",
        "clients.create",
        "clients.edit",
        "services.view",
        "appointments.view",
        "appointments.create",
        "appointments.edit",
        "analytics.view",
    ],
    "EMPLOYEE": [
        "appointments.view",
        "appointments.create",
        "clients.view",
    ],
    "RECEPTIONIST": [
        "appointments.view",
        "appointments.create",
        "appointments.edit",
        "clients.view",
        "clients.create",
        "clients.edit",
    ],
    "ACCOUNTANT": [
        "billing.view",
        "analytics.view",
    ],
    "MARKETING": [
        "clients.view",
        "analytics.view",
    ],
}


def create_default_permissions(
    db: Session
):
    for code, name in DEFAULT_PERMISSIONS:

        exists = db.query(
            Permission
        ).filter(
            Permission.code == code
        ).first()

        if not exists:
            db.add(
                Permission(
                    code=code,
                    name=name
                )
            )

    db.commit()


def create_default_roles(
    db: Session,
    company: Company
):
    create_default_permissions(db)

    permissions = {
        permission.code: permission
        for permission in db.query(
            Permission
        ).all()
    }

    for role_code, permission_codes in DEFAULT_ROLES.items():

        existing_role = db.query(Role).filter(
            Role.company_id == company.id,
            Role.code == role_code
        ).first()

        if existing_role:
            continue

        role = Role(
            company_id=company.id,
            code=role_code,
            name=role_code
        )

        role.permissions = [
            permissions[p]
            for p in permission_codes
        ]

        db.add(role)

    db.commit()


def create_owner_membership(
    db: Session,
    company: Company,
    user: User
):
    existing = db.query(
        CompanyMembership
    ).filter(
        CompanyMembership.company_id == company.id,
        CompanyMembership.user_id == user.id
    ).first()

    if existing:
        return existing

    membership = CompanyMembership(
        company_id=company.id,
        user_id=user.id,
        is_owner=True,
        status="active"
    )

    db.add(membership)

    db.commit()
    db.refresh(membership)

    owner_role = db.query(
        Role
    ).filter(
        Role.company_id == company.id,
        Role.code == "OWNER"
    ).first()

    if owner_role:
        membership.roles.append(
            owner_role
        )

    db.commit()

    return membership
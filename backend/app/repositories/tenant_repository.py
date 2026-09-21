from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant


class TenantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, tenant: Tenant) -> Tenant:
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def list_all(self) -> list[Tenant]:
        statement = select(Tenant).order_by(Tenant.id)
        return list(self.db.scalars(statement))

    def get_by_id(self, tenant_id: int) -> Tenant | None:
        return self.db.get(Tenant, tenant_id)

    def update(self, tenant: Tenant, changes: dict[str, object]) -> Tenant:
        for field, value in changes.items():
            setattr(tenant, field, value)

        self.db.commit()
        self.db.refresh(tenant)
        return tenant

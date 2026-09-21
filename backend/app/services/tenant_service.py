from app.models.tenant import Tenant
from app.repositories.tenant_repository import TenantRepository
from app.schemas.tenant import TenantCreate, TenantUpdate


class TenantNotFoundError(Exception):
    def __init__(self, tenant_id: int) -> None:
        super().__init__(f"Tenant con id {tenant_id} no encontrado")


class TenantService:
    def __init__(self, repository: TenantRepository) -> None:
        self.repository = repository

    def create(self, data: TenantCreate) -> Tenant:
        tenant = Tenant(**data.model_dump())
        return self.repository.create(tenant)

    def list_all(self) -> list[Tenant]:
        return self.repository.list_all()

    def get_by_id(self, tenant_id: int) -> Tenant:
        tenant = self.repository.get_by_id(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id)
        return tenant

    def update(self, tenant_id: int, data: TenantUpdate) -> Tenant:
        tenant = self.get_by_id(tenant_id)
        changes = data.model_dump(exclude_unset=True)
        return self.repository.update(tenant, changes)

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.db.init_db import init_db
from app.models import Tenant, User
from scripts.create_business import create_business


def test_concurrent_business_setup_is_atomic_and_does_not_reset_password(postgres_engine):
    init_db(postgres_engine)
    def provision(_):
        return create_business(postgres_engine, name="Negocio sintético",
                               email="admin.demo@example.com", password="synthetic-business-password")
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(provision, range(2)))
    assert len({result.tenant_id for result in results}) == 1
    assert sum(result.business_created for result in results) == 1
    assert sum(result.administrator_created for result in results) == 1
    repeat = create_business(postgres_engine, name="Negocio sintético",
                             email="admin.demo@example.com", password="another-synthetic-password")
    with Session(postgres_engine) as db:
        user = db.get(User, repeat.user_id)
        assert user.rol == "admin_tenant" and user.tenant_id == repeat.tenant_id
        assert verify_password("synthetic-business-password", user.password_hash)
        assert db.scalar(select(func.count()).select_from(Tenant)) == 1
        assert db.scalar(select(func.count()).select_from(User)) == 1
    with pytest.raises(ValueError):
        create_business(postgres_engine, name="Otro negocio", email="admin.demo@example.com",
                        password="synthetic-business-password")
    with Session(postgres_engine) as db:
        assert db.scalar(select(func.count()).select_from(Tenant)) == 1

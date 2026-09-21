"""Crea datos mínimos y repetibles para la demostración local del Sprint 0."""

from datetime import datetime

from sqlalchemy import func, select

from app.core.security import get_password_hash
from app.db.connection import SessionLocal
from app.db.init_db import init_db
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo123"
DEMO_TENANT = "Cafetería Horizonte"


def get_or_create_tenant() -> Tenant:
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.nombre == DEMO_TENANT))
        if tenant is None:
            tenant = Tenant(nombre=DEMO_TENANT, estado="activo")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        return tenant


def seed_user(tenant_id: int) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.correo == DEMO_EMAIL))
        if user is None:
            db.add(
                User(
                    tenant_id=tenant_id,
                    nombre="Usuario de demostración",
                    correo=DEMO_EMAIL,
                    password_hash=get_password_hash(DEMO_PASSWORD),
                    rol="usuario_negocio",
                    estado="activo",
                )
            )
            db.commit()


def seed_reviews(tenant_id: int) -> None:
    with SessionLocal() as db:
        review_count = db.scalar(
            select(func.count())
            .select_from(Review)
            .where(Review.tenant_id == tenant_id)
        )
        if review_count:
            return

        db.add_all(
            [
                Review(
                    tenant_id=tenant_id,
                    autor="Mariana",
                    contenido="El servicio fue rápido y el personal muy amable.",
                    fecha=datetime(2026, 9, 18, 9, 30),
                    fuente="Google",
                    puntuacion=5,
                    estado="atendida",
                    categoria="servicio",
                    prioridad="baja",
                ),
                Review(
                    tenant_id=tenant_id,
                    autor="Carlos",
                    contenido="El producto llegó bien, aunque el tiempo de espera fue largo.",
                    fecha=datetime(2026, 9, 19, 14, 15),
                    fuente="Facebook",
                    puntuacion=3,
                    estado="en_revision",
                    categoria="tiempo_espera",
                    prioridad="media",
                ),
                Review(
                    tenant_id=tenant_id,
                    autor=None,
                    contenido="Me gustaría encontrar más opciones sin azúcar.",
                    fecha=datetime(2026, 9, 20, 11, 0),
                    fuente="Formulario web",
                    puntuacion=4,
                    estado="nueva",
                    categoria=None,
                    prioridad=None,
                ),
            ]
        )
        db.commit()


def main() -> None:
    init_db()
    tenant = get_or_create_tenant()
    seed_user(tenant.id)
    seed_reviews(tenant.id)
    print("Datos de demostración listos.")
    print(f"Usuario: {DEMO_EMAIL}")
    print(f"Contraseña: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()

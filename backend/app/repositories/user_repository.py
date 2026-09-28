from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Acceso a usuarios sin reglas de negocio ni detalles HTTP."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_correo(self, correo: str) -> User | None:
        return self.db.scalar(select(User).where(User.correo == correo.lower()))

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def list_by_tenant(self, tenant_id: int) -> list[User]:
        statement = select(User).where(User.tenant_id == tenant_id).order_by(User.id)
        return list(self.db.scalars(statement))

    def create(self, user: User) -> User:
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except SQLAlchemyError:
            self.db.rollback()
            raise

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
    )
    autor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fuente: Mapped[str] = mapped_column(String(100), nullable=False)
    puntuacion: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(50), nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prioridad: Mapped[str | None] = mapped_column(String(50), nullable=True)

"""Asset and net-worth snapshot models (Phase 3)."""

from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.scoping import UserOwnedMixin


class AssetType(str, enum.Enum):
    CASH = "cash"
    INVESTMENT = "investment"
    REAL_ESTATE = "real_estate"
    VEHICLE = "vehicle"
    OTHER = "other"


_MONEY = Numeric(12, 2)


class Asset(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, native_enum=False, length=20), nullable=False
    )
    current_value: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))


class NetWorthSnapshot(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "net_worth_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    assets_total: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    liabilities_total: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    net_worth: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)

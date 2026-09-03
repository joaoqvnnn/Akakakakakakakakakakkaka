from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProductStatus(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"


class OrderStatus(str, PyEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentMethod(str, PyEnum):
    BALANCE = "balance"
    PIX = "pix"
    ADMIN = "admin"


class TransactionType(str, PyEnum):
    DEPOSIT = "deposit"
    PURCHASE = "purchase"
    GIFT_CARD = "gift_card"
    ADMIN_ADD = "admin_add"
    ADMIN_REMOVE = "admin_remove"
    AFFILIATE_COMMISSION = "affiliate_commission"
    AFFILIATE_CONVERT = "affiliate_convert"
    REFUND = "refund"


class GiftCardStatus(str, PyEnum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    DISABLED = "disabled"


class WithdrawStatus(str, PyEnum):
    PENDING = "pending"
    PAID = "paid"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram id
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total_spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total_deposited: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    whatsapp: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    referred_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    total_referrals: Mapped[int] = mapped_column(Integer, default=0)
    affiliate_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    affiliate_earned_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )
    affiliate_points: Mapped[int] = mapped_column(Integer, default=0)

    withdraw_password_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    emoji: Mapped[str] = mapped_column(String(16), default="📦")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200))
    emoji: Mapped[str] = mapped_column(String(16), default="🔥")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    stock_count: Mapped[int] = mapped_column(Integer, default=0)
    sold_count: Mapped[int] = mapped_column(Integer, default=0)
    warranty_days: Mapped[int] = mapped_column(Integer, default=30)
    validity_days: Mapped[int] = mapped_column(Integer, default=30)
    delivery_type: Mapped[str] = mapped_column(String(40), default="login_password")
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus), default=ProductStatus.ACTIVE
    )
    image_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class StockItem(Base):
    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    is_sold: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), default=PaymentMethod.BALANCE
    )
    delivery_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivery_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delivery_whatsapp: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    bonus_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING
    )
    gateway: Mapped[str] = mapped_column(String(40), default="mercadopago")
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    copy_paste: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qr_code_base64: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    admin_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    payment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GiftCard(Base):
    __tablename__ = "gift_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    uses_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[GiftCardStatus] = mapped_column(
        Enum(GiftCardStatus), default=GiftCardStatus.ACTIVE
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GiftCardRedemption(Base):
    __tablename__ = "gift_card_redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gift_card_id: Mapped[int] = mapped_column(Integer, ForeignKey("gift_cards.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StockAlert(Base):
    __tablename__ = "stock_alerts"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_alert_user_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AffiliateWithdraw(Base):
    __tablename__ = "affiliate_withdraws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[WithdrawStatus] = mapped_column(
        Enum(WithdrawStatus), default=WithdrawStatus.PENDING
    )
    payment_method: Mapped[str] = mapped_column(String(40), default="pending")
    pix_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pix_key_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    bank_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    agency: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    account: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    holder_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    holder_document: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    parse_mode: Mapped[str] = mapped_column(String(16), default="HTML")
    media_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    buttons: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

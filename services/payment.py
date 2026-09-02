from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import mercadopago
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Payment, PaymentStatus, PaymentMethod, TransactionType
from services.balance import BalanceService
from services.settings_service import SettingsService


class PaymentService:
    """PIX automático Mercado Pago + crédito de saldo (idempotente)."""

    def __init__(self, access_token: Optional[str] = None):
        self._token = access_token

    async def _resolve_token(self, session: AsyncSession) -> str:
        # Prioridade: config do admin no banco → .env
        db_token = await SettingsService.get(session, "mp_access_token")
        token = (db_token or self._token or settings.MP_ACCESS_TOKEN or "").strip()
        if not token:
            raise RuntimeError("Token Mercado Pago não configurado")
        return token

    async def _sdk(self, session: AsyncSession):
        token = await self._resolve_token(session)
        return mercadopago.SDK(token)

    async def create_pix(
        self,
        session: AsyncSession,
        user_id: int,
        amount: Decimal,
        related_product_id: Optional[int] = None,
        related_quantity: Optional[int] = None,
    ) -> Payment:
        pix_min = Decimal(str(await SettingsService.get(session, "pix_min", settings.PIX_MIN_VALUE)))
        pix_max = Decimal(str(await SettingsService.get(session, "pix_max", settings.PIX_MAX_VALUE)))
        exp_min = await SettingsService.get_int(session, "pix_expiration_minutes") or settings.PIX_EXPIRATION_MINUTES

        if amount < pix_min:
            raise ValueError(f"Valor mínimo: R$ {pix_min:.2f}")
        if amount > pix_max:
            raise ValueError(f"Valor máximo: R$ {pix_max:.2f}")

        bonus = Decimal("0.00")
        bonus_enabled = await SettingsService.get_bool(session, "bonus_enabled")
        if bonus_enabled:
            bonus_pct = Decimal(str(await SettingsService.get(session, "bonus_percent", "0")))
            bonus_min = Decimal(str(await SettingsService.get(session, "bonus_min_value", "0")))
            if amount >= bonus_min and bonus_pct > 0:
                bonus = (amount * bonus_pct / Decimal("100")).quantize(Decimal("0.01"))

        total_credited = amount + bonus
        external_ref = str(uuid4())

        sdk = await self._sdk(session)
        payment_data = {
            "transaction_amount": float(amount),
            "description": f"Recarga {settings.STORE_NAME}",
            "payment_method_id": "pix",
            "payer": {"email": f"user{user_id}@telegram.local"},
            "external_reference": external_ref,
        }
        if settings.MP_NOTIFICATION_URL:
            payment_data["notification_url"] = settings.MP_NOTIFICATION_URL

        result = sdk.payment().create(payment_data)
        response = result.get("response", {})
        if result.get("status") not in (200, 201):
            raise RuntimeError(f"Erro Mercado Pago: {response}")

        mp_id = str(response["id"])
        pix_data = response.get("point_of_interaction", {}).get("transaction_data", {})
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=exp_min)

        payment = Payment(
            user_id=user_id,
            amount=amount,
            bonus_amount=bonus,
            total_credited=total_credited,
            status=PaymentStatus.PENDING,
            method=PaymentMethod.PIX,
            gateway="mercadopago",
            gateway_id=mp_id,
            pix_copy_paste=pix_data.get("qr_code"),
            qr_code_base64=pix_data.get("qr_code_base64"),
            expires_at=expires_at,
            external_reference=external_ref,
            metadata_={"mp_status": response.get("status")},
            related_product_id=related_product_id,
            related_quantity=related_quantity,
        )
        session.add(payment)
        await session.flush()
        return payment

    async def process_webhook(
        self,
        session: AsyncSession,
        gateway_id: str,
    ) -> Optional[Payment]:
        """Confirma pagamento de forma idempotente (não credita 2 vezes)."""
        result = await session.execute(
            select(Payment).where(Payment.gateway_id == str(gateway_id))
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return None

        if payment.status == PaymentStatus.APPROVED:
            return payment  # já processado

        sdk = await self._sdk(session)
        mp_result = sdk.payment().get(gateway_id)
        mp_payment = mp_result.get("response", {})
        status = mp_payment.get("status")

        if status == "approved":
            payment.status = PaymentStatus.APPROVED
            payment.paid_at = datetime.now(timezone.utc)

            await BalanceService.add_balance(
                session=session,
                user_id=payment.user_id,
                amount=payment.amount,
                tx_type=TransactionType.DEPOSIT,
                description=f"Depósito PIX #{payment.uuid[:8]}",
                payment_id=payment.id,
            )
            if payment.bonus_amount > 0:
                await BalanceService.add_balance(
                    session=session,
                    user_id=payment.user_id,
                    amount=payment.bonus_amount,
                    tx_type=TransactionType.BONUS,
                    description=f"Bônus recarga #{payment.uuid[:8]}",
                    payment_id=payment.id,
                )
            await session.flush()
            return payment

        if status in ("rejected", "cancelled"):
            payment.status = (
                PaymentStatus.REJECTED if status == "rejected" else PaymentStatus.CANCELLED
            )
            await session.flush()
        elif status == "expired":
            payment.status = PaymentStatus.EXPIRED
            await session.flush()

        return payment

    async def expire_pending(self, session: AsyncSession) -> int:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Payment).where(
                Payment.status == PaymentStatus.PENDING,
                Payment.expires_at < now,
            )
        )
        payments = list(result.scalars().all())
        for p in payments:
            p.status = PaymentStatus.EXPIRED
        await session.flush()
        return len(payments)

    async def check_status(
        self,
        session: AsyncSession,
        payment_uuid: str,
    ) -> Optional[Payment]:
        result = await session.execute(
            select(Payment).where(Payment.uuid == payment_uuid)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        if payment.status == PaymentStatus.PENDING and payment.gateway_id:
            return await self.process_webhook(session, payment.gateway_id)
        return payment

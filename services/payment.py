from decimal import Decimal
from datetime import datetime, timedelta, timezone
import uuid as uuid_lib
import logging
from typing import Any, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Payment, PaymentStatus, TransactionType
from services.settings_service import SettingsService
from services.balance import BalanceService
from services.affiliate import AffiliateService

logger = logging.getLogger(__name__)


class PaymentService:
    def _mp_token_sync(self, token: str):
        import mercadopago

        return mercadopago.SDK(token)

    async def create_pix(
        self,
        session: AsyncSession,
        user_id: int,
        amount: Decimal,
        description: str = "Recarga",
        metadata: Optional[dict] = None,
    ) -> Tuple[Payment, Optional[str], Optional[str]]:
        token = await SettingsService.get(session, "mp_access_token") or settings.MP_ACCESS_TOKEN
        if not token:
            raise ValueError("Token Mercado Pago não configurado")

        exp_min = await SettingsService.get_int(session, "pix_expiration_minutes") or 10
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=exp_min)
        payment_uuid = str(uuid_lib.uuid4())

        bonus_percent = Decimal(
            str(await SettingsService.get(session, "bonus_percent") or "0")
        )
        bonus_min = Decimal(
            str(await SettingsService.get(session, "bonus_min_value") or "0")
        )
        bonus = Decimal("0")
        if amount >= bonus_min and bonus_percent > 0:
            bonus = (amount * bonus_percent / Decimal("100")).quantize(Decimal("0.01"))

        body = {
            "transaction_amount": float(amount),
            "description": description[:200],
            "payment_method_id": "pix",
            "payer": {
                "email": f"user{user_id}@larizinha.store",
            },
            "external_reference": payment_uuid,
            "metadata": metadata or {},
        }

        sdk = self._mp_token_sync(token)
        result = sdk.payment().create(body)
        resp = result.get("response") or {}

        if result.get("status") not in (200, 201):
            logger.error("MP create error: %s", result)
            raise ValueError(
                resp.get("message")
                or resp.get("error")
                or "Falha ao criar pagamento no Mercado Pago"
            )

        gateway_id = str(resp.get("id", ""))
        poi = (resp.get("point_of_interaction") or {}).get("transaction_data") or {}
        copy_paste = poi.get("qr_code")
        qr_base64 = poi.get("qr_code_base64")

        payment = Payment(
            uuid=payment_uuid,
            user_id=user_id,
            amount=amount,
            bonus_amount=bonus,
            status=PaymentStatus.PENDING,
            gateway="mercadopago",
            gateway_payment_id=gateway_id,
            copy_paste=copy_paste,
            qr_code_base64=qr_base64,
            expires_at=expires_at,
            metadata_json=metadata or {},
            description=description,
        )
        session.add(payment)
        await session.flush()
        return payment, qr_base64, copy_paste

    async def process_webhook(
        self, session: AsyncSession, gateway_payment_id: str
    ) -> Optional[Payment]:
        token = await SettingsService.get(session, "mp_access_token") or settings.MP_ACCESS_TOKEN
        if not token:
            return None

        sdk = self._mp_token_sync(token)
        result = sdk.payment().get(gateway_payment_id)
        resp = result.get("response") or {}
        if not resp:
            return None

        status_mp = (resp.get("status") or "").lower()
        external_ref = resp.get("external_reference")

        payment = None
        if external_ref:
            r = await session.execute(
                select(Payment).where(Payment.uuid == external_ref)
            )
            payment = r.scalar_one_or_none()
        if not payment:
            r = await session.execute(
                select(Payment).where(Payment.gateway_payment_id == str(gateway_payment_id))
            )
            payment = r.scalar_one_or_none()
        if not payment:
            return None

        if payment.status == PaymentStatus.APPROVED:
            return payment

        if status_mp == "approved":
            payment.status = PaymentStatus.APPROVED
            payment.paid_at = datetime.now(timezone.utc)
            total_credit = payment.amount + (payment.bonus_amount or Decimal("0"))
            await BalanceService.add_balance(
                session,
                payment.user_id,
                total_credit,
                TransactionType.DEPOSIT,
                description=f"PIX {payment.uuid}",
                payment_id=payment.id,
            )
            # Afiliados: comissão + pontos
            try:
                await AffiliateService.pay_commission(
                    session, payment.user_id, payment.amount
                )
                await AffiliateService.add_points_on_recharge(
                    session, payment.user_id
                )
            except Exception:
                logger.exception("Erro comissão afiliado")
            await session.flush()
            return payment

        if status_mp in ("cancelled", "rejected"):
            payment.status = PaymentStatus.CANCELLED
            await session.flush()
        elif status_mp == "expired":
            payment.status = PaymentStatus.EXPIRED
            await session.flush()

        return payment

    async def expire_pending(self, session: AsyncSession) -> int:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Payment).where(
                Payment.status == PaymentStatus.PENDING,
                Payment.expires_at.is_not(None),
                Payment.expires_at < now,
            )
        )
        items = list(result.scalars().all())
        for p in items:
            p.status = PaymentStatus.EXPIRED
        await session.flush()
        return len(items)

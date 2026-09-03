from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AffiliateWithdraw, WithdrawStatus, User
from services.settings_service import SettingsService
import hashlib


class WithdrawWebService:
    @staticmethod
    async def get_by_uuid(session: AsyncSession, uuid: str) -> Optional[AffiliateWithdraw]:
        result = await session.execute(
            select(AffiliateWithdraw).where(AffiliateWithdraw.uuid == uuid)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def check_web_password(session: AsyncSession, password: str) -> bool:
        expected = await SettingsService.get(session, "web_withdraw_password")
        if not expected:
            expected = "Larizinha@2026"
        return password == expected

    @staticmethod
    def check_user_withdraw_password(user: User, password: str, fallback_global: str) -> bool:
        if user.withdraw_password_hash:
            h = hashlib.sha256(password.encode("utf-8")).hexdigest()
            return h == user.withdraw_password_hash
        return password == fallback_global

    @staticmethod
    async def save_bank_data(
        session: AsyncSession,
        uuid: str,
        *,
        bank_code: str,
        bank_name: str,
        agency: str,
        agency_digit: str,
        account: str,
        account_digit: str,
        account_type: str,
        holder_name: str,
        holder_document: str,
        withdraw_password: str,
    ) -> AffiliateWithdraw:
        w = await WithdrawWebService.get_by_uuid(session, uuid)
        if not w:
            raise ValueError("Saque não encontrado")
        if w.status != WithdrawStatus.PENDING:
            raise ValueError("Este saque já foi processado")

        user = await session.get(User, w.user_id)
        if not user:
            raise ValueError("Usuário não encontrado")

        global_pwd = await SettingsService.get(session, "delivery_password") or "1234"
        if not WithdrawWebService.check_user_withdraw_password(
            user, withdraw_password, global_pwd
        ):
            raise ValueError("Senha de saque incorreta")

        w.payment_method = "bank_transfer"
        w.bank_code = bank_code
        w.bank_name = bank_name
        w.agency = f"{agency}-{agency_digit}" if agency_digit else agency
        w.account = f"{account}-{account_digit}" if account_digit else account
        w.account_type = account_type
        w.holder_name = holder_name
        w.holder_document = holder_document
        w.updated_at = datetime.now(timezone.utc)

        await session.flush()
        return w

    @staticmethod
    async def list_user_withdraws(
        session: AsyncSession, user_id: int, limit: int = 20
    ) -> list:
        result = await session.execute(
            select(AffiliateWithdraw)
            .where(AffiliateWithdraw.user_id == user_id)
            .order_by(AffiliateWithdraw.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

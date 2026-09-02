from decimal import Decimal

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import base64

from config import settings
from database.models import User, Payment, PaymentStatus
from keyboards.client import recharge_kb, pix_created_kb, main_menu_kb, back_kb
from services.payment import PaymentService
from services.settings_service import SettingsService

router = Router(name="wallet")
payment_service = PaymentService()

class PixStates(StatesGroup):
    waiting_value = State()

def _format_pix_text(payment: Payment, db_user: User, exp_min: int) -> str:
    return (
        f"💰 <b>Comprar Saldo com Pix Automático:</b>\n\n"
        f"⏱️ Expira em: <b>{exp_min} Minutos</b>\n"
        f"💵 Valor: <b>R$ {payment.amount:.2f}</b>\n"
        f"✨ ID da Recarga: <code>{payment.uuid}</code>\n\n"
        f"📃 <b>Atenção:</b> Este código é válido para apenas um único pagamento.\n"
        f"Se você utilizá-lo mais de uma vez, o saldo adicional será perdido "
        f"sem direito a reembolso.\n\n"
        f"💎 <b>Pix Copia e Cola:</b>\n"
        f"<code>{payment.pix_copy_paste or '—'}</code>\n\n"
        f"💡 Dica: Clique no código acima para copiar.\n\n"
        f"📊 <b>Dados:</b>\n"
        f"— 💰 Saldo Atual: <b>R$ {db_user.balance:.2f}</b>\n"
        f"— 🎁 Bônus à receber: <b>R$ {payment.bonus_amount:.2f}</b>\n"
        f"— 💸 Saldo após o pagamento: <b>R$ {db_user.balance + payment.total_credited:.2f}</b>\n\n"
        f"🇧🇷 Após o pagamento, seu saldo será liberado instantaneamente."
    )

@router.callback_query(F.data == "recharge")
async def cb_recharge(callback: CallbackQuery, db_user: User):
    text = (
        f"🆔 ID da Carteira: <code>{db_user.id}</code>\n"
        f"💰 Saldo Disponível: <b>R$ {db_user.balance:.2f}</b>\n\n"
        f"📍 Opte por <b>💠 Pix Rápido</b> para que seu saldo seja creditado imediatamente.\n\n"
        f"💡 Selecione uma opção para recarregar:"
    )
    await callback.message.edit_text(
        text, reply_markup=recharge_kb(), parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "pix_custom")
async def cb_pix_custom(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    pix_min = await SettingsService.get(session, "pix_min", str(settings.PIX_MIN_VALUE))
    bonus_pct = await SettingsService.get(session, "bonus_percent", "10")
    bonus_min = await SettingsService.get(session, "bonus_min_value", "10")

    await state.set_state(PixStates.waiting_value)
    await callback.message.edit_text(
        f"ℹ️ Informe o valor que deseja recarregar:\n\n"
        f"🔻 Recarga mínima: <b>R$ {pix_min}</b>\n\n"
        f"⚠️ Envie o valor agora.\n"
        f"Ao depositar você declara estar de acordo com /termos\n\n"
        f"🎁 Bônus de recarga: <b>{bonus_pct}%</b>\n"
        f"❗️ Mínimo para bônus: <b>R$ {bonus_min}</b>",
        reply_markup=back_kb("recharge"),
        parse_mode="HTML",
    )
    await callback.answer()

@router.message(PixStates.waiting_value)
async def process_pix_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
):
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = Decimal(raw)
    except Exception:
        await message.answer("❌ Valor inválido. Ex: 10 ou 15.50")
        return

    await state.clear()
    wait = await message.answer("⏳ Gerando pagamento...")

    try:
        payment = await payment_service.create_pix(session, db_user.id, amount)
    except ValueError as e:
        await wait.edit_text(f"❌ {e}")
        return
    except Exception:
        await wait.edit_text("❌ Erro ao gerar PIX. Verifique o token Mercado Pago.")
        return

    exp = await SettingsService.get_int(session, "pix_expiration_minutes") or 10
    text = _format_pix_text(payment, db_user, exp)
    kb = pix_created_kb(payment.uuid)

    if payment.qr_code_base64:
        try:
            raw_b64 = payment.qr_code_base64
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            photo = BufferedInputFile(
                base64.b64decode(raw_b64), filename="pix.png"
            )
            await wait.delete()
            await message.answer_photo(
                photo, caption=text, reply_markup=kb, parse_mode="HTML"
            )
            return
        except Exception:
            pass

    await wait.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("pix_for_product:"))
async def cb_pix_for_product(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    parts = callback.data.split(":")
    product_id = int(parts[1])
    quantity = int(parts[2])
    amount = Decimal(parts[3])

    await callback.message.edit_text("⏳ Gerando pagamento...")
    try:
        payment = await payment_service.create_pix(
            session,
            db_user.id,
            amount,
            related_product_id=product_id,
            related_quantity=quantity,
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ {e}", reply_markup=main_menu_kb())
        await callback.answer()
        return

    exp = await SettingsService.get_int(session, "pix_expiration_minutes") or 10
    text = _format_pix_text(payment, db_user, exp)
    await callback.message.edit_text(
        text, reply_markup=pix_created_kb(payment.uuid), parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("check_pix:"))
async def cb_check_pix(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    uuid = callback.data.split(":", 1)[1]
    payment = await payment_service.check_status(session, uuid)

    if not payment:
        await callback.answer("Pagamento não encontrado.", show_alert=True)
        return

    await session.refresh(db_user)

    if payment.status == PaymentStatus.APPROVED:
        await callback.message.edit_text(
            f"✅ <b>PAGAMENTO APROVADO!</b>\n\n"
            f"💰 Valor: <b>R$ {payment.amount:.2f}</b>\n"
            f"🎁 Bônus: <b>R$ {payment.bonus_amount:.2f}</b>\n"
            f"💳 Saldo atual: <b>R$ {db_user.balance:.2f}</b>",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer("✅ Confirmado!")
    elif payment.status == PaymentStatus.EXPIRED:
        await callback.message.edit_text(
            f"⌛️ <b>PAGAMENTO PIX EXPIRADO</b>\n\n"
            f"⚠️ O tempo limite para realizar este pagamento foi excedido.\n\n"
            f"🆔 Referência: <code>{payment.uuid}</code>\n"
            f"💸 Valor: <b>R$ {payment.amount:.2f}</b>",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer("Expirado", show_alert=True)
    else:
        await callback.answer(
            "⏳ Ainda não reconhecemos o pagamento. Aguarde alguns segundos e tente de novo.",
            show_alert=True,
        )

@router.message(Command("pix"))
async def cmd_pix(message: Message, session: AsyncSession, db_user: User):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Formato incorreto.\n"
            "Use:\n<code>/pix 10</code>\nou\n<code>/pix 5.25</code>",
            parse_mode="HTML",
        )
        return
    try:
        amount = Decimal(parts[1].replace(",", "."))
    except Exception:
        await message.answer("❌ Valor inválido.")
        return

    wait = await message.answer("⏳ Gerando pagamento...")
    try:
        payment = await payment_service.create_pix(session, db_user.id, amount)
    except Exception as e:
        await wait.edit_text(f"❌ {e}")
        return

    exp = await SettingsService.get_int(session, "pix_expiration_minutes") or 10
    await wait.edit_text(
        _format_pix_text(payment, db_user, exp),
        reply_markup=pix_created_kb(payment.uuid),
        parse_mode="HTML",
    )

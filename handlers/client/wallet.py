from decimal import Decimal

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Payment, PaymentStatus
from keyboards.client_dynamic import recharge_kb, pix_created_kb, main_menu_kb, back_kb
from services.payment import PaymentService
from services.settings_service import SettingsService
from services.messages import MessageService

router = Router(name="wallet")
payment_service = PaymentService()


class RechargeStates(StatesGroup):
    waiting_amount = State()


@router.callback_query(F.data == "recharge")
async def cb_recharge(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    text = (
        f"🆔 ID da Carteira: <code>{db_user.id}</code>\n"
        f"💰 Saldo Disponível: <b>R$ {db_user.balance:.2f}</b>\n\n"
        f"📍 Opte por <b>💠 Pix Rápido</b> para crédito imediato.\n\n"
        f"💡 Selecione uma opção para recarregar:"
    )
    kb = await recharge_kb(session)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "pix_custom")
async def cb_pix_custom(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    pix_min = await SettingsService.get(session, "pix_min")
    bonus = await SettingsService.get(session, "bonus_percent")
    bonus_min = await SettingsService.get(session, "bonus_min_value")
    await state.set_state(RechargeStates.waiting_amount)
    kb = await back_kb(session, "recharge")
    await callback.message.edit_text(
        f"ℹ️ Informe o valor que deseja recarregar:\n\n"
        f"🔻 Recarga mínima: <b>R$ {pix_min}</b>\n\n"
        f"⚠️ Envie o valor agora.\n"
        f"Ao depositar você declara estar de acordo com /termos\n\n"
        f"🎁 Bônus de recarga: <b>{bonus}%</b>\n"
        f"❗️ Mínimo para bônus: <b>R$ {bonus_min}</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(RechargeStates.waiting_amount)
async def process_amount(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    try:
        amount = Decimal((message.text or "").replace(",", ".").strip())
    except Exception:
        await message.answer("❌ Valor inválido.")
        return

    pix_min = Decimal(str(await SettingsService.get(session, "pix_min") or "4"))
    pix_max = Decimal(str(await SettingsService.get(session, "pix_max") or "5000"))
    if amount < pix_min:
        await message.answer(f"❌ Mínimo R$ {pix_min:.2f}")
        return
    if amount > pix_max:
        await message.answer(f"❌ Máximo R$ {pix_max:.2f}")
        return

    await state.clear()
    await message.answer("⏳ Gerando pagamento...")
    await _create_and_send_pix(message, session, db_user, amount)


@router.message(Command("pix"))
async def cmd_pix(message: Message, session: AsyncSession, db_user: User):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Você enviou em um formato incorreto. Envie /pix e o valor.\n\n"
            "Exemplo:\n/pix 10\n/pix 5.25"
        )
        return
    try:
        amount = Decimal(parts[1].replace(",", ".").strip())
    except Exception:
        await message.answer("❌ Valor inválido. Ex: /pix 10")
        return

    pix_min = Decimal(str(await SettingsService.get(session, "pix_min") or "4"))
    if amount < pix_min:
        await message.answer(f"❌ Mínimo R$ {pix_min:.2f}")
        return

    await message.answer("⏳ Gerando pagamento...")
    await _create_and_send_pix(message, session, db_user, amount)


async def _create_and_send_pix(message, session, db_user, amount: Decimal):
    bonus_percent = Decimal(
        str(await SettingsService.get(session, "bonus_percent") or "0")
    )
    bonus_min = Decimal(
        str(await SettingsService.get(session, "bonus_min_value") or "0")
    )
    bonus = Decimal("0")
    if amount >= bonus_min and bonus_percent > 0:
        bonus = (amount * bonus_percent / Decimal("100")).quantize(Decimal("0.01"))

    try:
        payment, qr_b64, copy_paste = await payment_service.create_pix(
            session,
            user_id=db_user.id,
            amount=amount,
            description=f"Recarga saldo user {db_user.id}",
            metadata={"purpose": "recharge"},
        )
    except Exception as e:
        await message.answer(
            f"❌ Erro ao gerar PIX: {e}",
            reply_markup=await main_menu_kb(session),
        )
        return

    exp = await SettingsService.get(session, "pix_expiration_minutes")
    text = (
        f"💰 <b>Comprar Saldo com Pix Automático</b>\n\n"
        f"⏱️ Expira em: <b>{exp} Minutos</b>\n"
        f"💵 Valor: <b>R$ {payment.amount:.2f}</b>\n"
        f"✨ ID da Recarga: <code>{payment.uuid}</code>\n\n"
        f"📃 Este código vale para um único pagamento.\n\n"
        f"💎 <b>Pix Copia e Cola:</b>\n"
        f"<code>{copy_paste or payment.copy_paste or '—'}</code>\n\n"
        f"💡 Clique no código para copiar.\n\n"
        f"📊 Dados:\n"
        f"— 💰 Saldo Atual: R$ {db_user.balance:.2f}\n"
        f"— 🎁 Bônus à receber: R$ {bonus:.2f}\n"
        f"— 💸 Saldo após o pagamento: R$ {db_user.balance + amount + bonus:.2f}\n\n"
        f"🇧🇷 Após o pagamento, o saldo é liberado automaticamente."
    )
    kb = await pix_created_kb(session, payment.uuid)

    if payment.qr_code_base64 or qr_b64:
        import base64
        from aiogram.types import BufferedInputFile

        raw = payment.qr_code_base64 or qr_b64
        if "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            photo = BufferedInputFile(base64.b64decode(raw), filename="qr.png")
            await message.answer_photo(
                photo, caption=text, reply_markup=kb, parse_mode="HTML"
            )
            return
        except Exception:
            pass

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("check_pix:"))
async def cb_check_pix(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    uuid = callback.data.split(":", 1)[1]
    result = await session.execute(select(Payment).where(Payment.uuid == uuid))
    payment = result.scalar_one_or_none()
    if not payment or payment.user_id != db_user.id:
        await callback.answer("Pagamento não encontrado.", show_alert=True)
        return

    if payment.status == PaymentStatus.APPROVED:
        await callback.answer("✅ Já aprovado!", show_alert=True)
        await callback.message.answer(
            f"✅ Pagamento confirmado. Saldo: R$ {db_user.balance:.2f}",
            reply_markup=await main_menu_kb(session),
        )
        return

    if payment.status == PaymentStatus.EXPIRED:
        tpl = await MessageService.get_rendered(
            session,
            "payment_expired",
            payment_id=payment.uuid,
            amount=f"{payment.amount:.2f}",
        )
        await callback.message.edit_text(
            tpl["content"],
            reply_markup=await main_menu_kb(session),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    tpl = await MessageService.get_rendered(session, "pix_not_found")
    await callback.answer(tpl["content"][:180], show_alert=True)

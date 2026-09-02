from decimal import Decimal

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Product, ProductStatus, StockItem, AdminLog
from keyboards.admin import admin_cfg_logins_kb
from services.settings_service import SettingsService
from handlers.admin.panel import is_admin

router = Router(name="admin_logins")


class LoginStates(StatesGroup):
    add_bulk = State()
    remove_one = State()
    remove_platform = State()
    price_one = State()
    price_all = State()


def _parse_line(line: str, sep: str) -> dict | None:
    parts = [p.strip() for p in line.split(sep)]
    if not parts or not parts[0]:
        return None
    name = parts[0]
    price = Decimal("0")
    description = ""
    email = ""
    password = ""
    duration = 30
    if len(parts) >= 2 and parts[1]:
        try:
            price = Decimal(parts[1].replace(",", "."))
        except Exception:
            pass
    if len(parts) >= 3:
        description = parts[2]
    if len(parts) >= 4:
        email = parts[3]
    if len(parts) >= 5:
        password = parts[4]
    if len(parts) >= 6 and parts[5].isdigit():
        duration = int(parts[5])
    if email and password:
        content = f"{email}:{password}"
    elif email:
        content = email
    else:
        content = password
    return {
        "name": name,
        "price": price,
        "description": description,
        "content": content,
        "duration": duration,
    }


async def _get_or_create(
    session: AsyncSession, name: str, price: Decimal, description: str, duration: int
) -> Product:
    result = await session.execute(
        select(Product).where(func.lower(Product.name) == name.lower())
    )
    product = result.scalar_one_or_none()
    if product:
        if price > 0:
            product.price = price
        if description:
            product.description = description
        if duration:
            product.warranty_days = duration
            product.validity_days = duration
        return product
    product = Product(
        name=name,
        emoji="🔥",
        price=price if price > 0 else Decimal("1.00"),
        description=description or None,
        warranty_days=duration or 30,
        validity_days=duration or 30,
        delivery_type="login_password",
        status=ProductStatus.ACTIVE,
        stock_count=0,
    )
    session.add(product)
    await session.flush()
    return product


@router.callback_query(F.data == "admin:cfg_logins")
async def cb_cfg_logins(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    count = (
        await session.execute(
            select(func.count(StockItem.id)).where(StockItem.is_sold.is_(False))
        )
    ).scalar_one() or 0
    sep = await SettingsService.get(session, "separator") or "==="
    text = (
        f"<b>CONFIGURAR LOGINS</b>\n\n"
        f"LOGINS NO ESTOQUE: <b>{count}</b>\n\n"
        f"Formato (separador <code>{sep}</code>):\n"
        f"<code>NOME{sep}VALOR{sep}DESCRICAO{sep}EMAIL{sep}SENHA{sep}DURACAO</code>"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_logins_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.in_({"admin:login_add", "admin:stock_supply"}))
async def cb_login_add(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    sep = await SettingsService.get(session, "separator") or "==="
    await state.set_state(LoginStates.add_bulk)
    await callback.message.edit_text(
        f"➕ <b>ADICIONAR LOGIN</b>\n\n"
        f"Uma linha por login:\n"
        f"<code>NOME{sep}VALOR{sep}DESCRICAO{sep}EMAIL{sep}SENHA{sep}DURACAO</code>\n\n"
        f"/cancelar para sair.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(LoginStates.add_bulk)
async def process_add(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.", reply_markup=admin_cfg_logins_kb())
        return
    sep = await SettingsService.get(session, "separator") or "==="
    lines = [ln.strip() for ln in (message.text or "").splitlines() if ln.strip()]
    added = 0
    for line in lines:
        parsed = _parse_line(line, sep)
        if not parsed:
            continue
        product = await _get_or_create(
            session, parsed["name"], parsed["price"], parsed["description"], parsed["duration"]
        )
        if parsed["content"]:
            session.add(StockItem(product_id=product.id, content=parsed["content"]))
            product.stock_count = (product.stock_count or 0) + 1
            if product.status == ProductStatus.OUT_OF_STOCK:
                product.status = ProductStatus.ACTIVE
            added += 1
    session.add(AdminLog(admin_id=db_user.id, action="stock_add_bulk", details={"added": added}))
    await state.clear()
    await message.answer(
        f"✅ Unidades adicionadas: <b>{added}</b>",
        parse_mode="HTML",
        reply_markup=admin_cfg_logins_kb(),
    )


@router.callback_query(F.data == "admin:login_remove")
async def cb_remove(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    sep = await SettingsService.get(session, "separator") or "==="
    await state.set_state(LoginStates.remove_one)
    await callback.message.edit_text(
        f"➖ Envie: <code>SERVICO{sep}EMAIL</code>", parse_mode="HTML"
    )
    await callback.answer()


@router.message(LoginStates.remove_one)
async def process_remove(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    sep = await SettingsService.get(session, "separator") or "==="
    parts = [p.strip() for p in (message.text or "").split(sep)]
    await state.clear()
    if len(parts) < 2:
        await message.answer(f"❌ Use SERVICO{sep}EMAIL")
        return
    name, email = parts[0], parts[1]
    result = await session.execute(select(Product).where(func.lower(Product.name) == name.lower()))
    product = result.scalar_one_or_none()
    if not product:
        await message.answer("❌ Serviço não encontrado.")
        return
    result = await session.execute(
        select(StockItem).where(
            StockItem.product_id == product.id,
            StockItem.is_sold.is_(False),
            StockItem.content.ilike(f"%{email}%"),
        )
    )
    items = list(result.scalars().all())
    for item in items:
        await session.delete(item)
    product.stock_count = max(0, (product.stock_count or 0) - len(items))
    await message.answer(
        f"✅ Removidos: <b>{len(items)}</b>", parse_mode="HTML", reply_markup=admin_cfg_logins_kb()
    )


@router.callback_query(F.data == "admin:login_remove_platform")
async def cb_rm_plat(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(LoginStates.remove_platform)
    await callback.message.edit_text("🗑 Nome da plataforma para zerar estoque:")
    await callback.answer()


@router.message(LoginStates.remove_platform)
async def process_rm_plat(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    name = (message.text or "").strip()
    await state.clear()
    result = await session.execute(select(Product).where(func.lower(Product.name) == name.lower()))
    product = result.scalar_one_or_none()
    if not product:
        await message.answer("❌ Não encontrado.")
        return
    result = await session.execute(
        select(StockItem).where(StockItem.product_id == product.id, StockItem.is_sold.is_(False))
    )
    items = list(result.scalars().all())
    for item in items:
        await session.delete(item)
    product.stock_count = 0
    await message.answer(
        f"✅ Removidos {len(items)} de {product.name}.", reply_markup=admin_cfg_logins_kb()
    )


@router.callback_query(F.data == "admin:stock_clear")
async def cb_clear(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    result = await session.execute(select(StockItem).where(StockItem.is_sold.is_(False)))
    items = list(result.scalars().all())
    for item in items:
        await session.delete(item)
    for p in (await session.execute(select(Product))).scalars().all():
        p.stock_count = 0
    await callback.message.edit_text(
        f"⚠️ Zerado. Removidos: <b>{len(items)}</b>",
        reply_markup=admin_cfg_logins_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:login_price")
async def cb_price(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    sep = await SettingsService.get(session, "separator") or "==="
    await state.set_state(LoginStates.price_one)
    await callback.message.edit_text(f"💰 Envie: <code>SERVICO{sep}VALOR</code>", parse_mode="HTML")
    await callback.answer()


@router.message(LoginStates.price_one)
async def process_price(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    sep = await SettingsService.get(session, "separator") or "==="
    parts = [p.strip() for p in (message.text or "").split(sep)]
    await state.clear()
    if len(parts) < 2:
        await message.answer("❌ Formato inválido.")
        return
    try:
        price = Decimal(parts[1].replace(",", "."))
    except Exception:
        await message.answer("❌ Valor inválido.")
        return
    result = await session.execute(select(Product).where(func.lower(Product.name) == parts[0].lower()))
    product = result.scalar_one_or_none()
    if not product:
        await message.answer("❌ Serviço não encontrado.")
        return
    product.price = price
    await message.answer(
        f"✅ {product.name} = <b>R$ {price:.2f}</b>",
        parse_mode="HTML",
        reply_markup=admin_cfg_logins_kb(),
    )


@router.callback_query(F.data == "admin:login_price_all")
async def cb_price_all(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(LoginStates.price_all)
    await callback.message.edit_text("🔥 Novo valor para TODOS os produtos:")
    await callback.answer()


@router.message(LoginStates.price_all)
async def process_price_all(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    try:
        price = Decimal((message.text or "").strip().replace(",", "."))
    except Exception:
        await message.answer("❌ Valor inválido.")
        return
    await state.clear()
    products = list((await session.execute(select(Product))).scalars().all())
    for p in products:
        p.price = price
    await message.answer(
        f"✅ {len(products)} produtos → R$ {price:.2f}",
        reply_markup=admin_cfg_logins_kb(),
    )


@router.callback_query(F.data == "admin:stock_view")
async def cb_stock_view(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    products = list(
        (await session.execute(select(Product).order_by(Product.name))).scalars().all()
    )
    if not products:
        text = "Nenhum produto."
    else:
        lines = ["📋 <b>ESTOQUE DETALHADO</b>\n"]
        for p in products:
            emoji = "⚠️" if (p.stock_count or 0) <= 5 else "✅"
            lines.append(f"{emoji} <b>{p.name}</b> — R$ {p.price:.2f} | <b>{p.stock_count}</b>")
        text = "\n".join(lines)
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_logins_kb(), parse_mode="HTML"
    )
    await callback.answer()

import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm


def build_order_pdf(
    *,
    store_name: str,
    product_name: str,
    order_uuid: str,
    price: str,
    date_str: str,
    expires_str: str,
    payment_method: str,
    delivery_content: str,
    activation_help: str,
) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    def line(text: str, size: int = 11, gap: float = 0.55):
        nonlocal y
        c.setFont("Helvetica", size)
        for part in str(text).split("\n"):
            c.drawString(2 * cm, y, part[:110])
            y -= gap * cm
            if y < 2 * cm:
                c.showPage()
                y = height - 2 * cm
                c.setFont("Helvetica", size)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, store_name)
    y -= 1 * cm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(2 * cm, y, "Compra realizada com sucesso")
    y -= 1 * cm

    line(f"Produto: {product_name}", 12)
    line(f"Valor: R$ {price}")
    line(f"Data/Hora: {date_str}")
    line(f"Vencimento/período: {expires_str}")
    line(f"Pagamento: {payment_method}")
    line(f"Pedido: {order_uuid}")
    y -= 0.3 * cm
    line("=== DADOS DE ACESSO ===", 12)
    line(delivery_content or "—")
    y -= 0.3 * cm
    line("=== COMO ATIVAR ===", 12)
    line(activation_help or "Siga as instruções do serviço.")
    y -= 0.5 * cm
    line("Documento confidencial. Não compartilhe.", 9)

    c.showPage()
    c.save()
    return buffer.getvalue()

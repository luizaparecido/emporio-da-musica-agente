"""Tools de pedidos, devolução e encaminhamento. Pedidos sempre exigem verificação."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from emporio_agent.config import Clock
from emporio_agent.data.repository import StoreRepository
from emporio_agent.domain.models import Order, OrderStatus
from emporio_agent.domain.money import format_brl
from emporio_agent.memory.store import SessionStore
from emporio_agent.services.orders import OrderService, VerificationFailed
from emporio_agent.services.returns import Eligibility, Outcome, ReturnReason, check_eligibility
from emporio_agent.services.tickets import TicketService
from emporio_agent.tools.presenters import format_date
from emporio_agent.tools.registry import Tool

MAX_FAILED_VERIFICATIONS = 3
FAILED_MESSAGE = "Não foi possível confirmar esses dados. Não informe se o pedido existe."
LOCKED_MESSAGE = (
    "Limite de tentativas de verificação atingido nesta conversa. Não tente de novo: "
    "encaminhe o cliente à equipe pelo telefone (67) 3341-4444."
)

SHIPPING_DATA_LIMIT = (
    "O sistema não informa a data de envio, a transportadora nem o motivo de atraso. Não cite esses dados. "
    "compra_realizada_em é a data da compra, não a do envio."
)

STATUS_LABELS = {
    OrderStatus.PENDING: "Pendente: aguardando confirmação",
    OrderStatus.CONFIRMED: "Confirmado: ainda não despachado",
    OrderStatus.SHIPPED: "Enviado",
    OrderStatus.DELIVERED: "Entregue",
    OrderStatus.CANCELLED: "Cancelado",
}
PAYMENT_LABELS = {"pix": "PIX", "boleto": "Boleto", "debit": "Cartão de débito"}


def _payment_label(method: str) -> str:
    if method.startswith("credit_"):
        return f"Cartão de crédito em {method.removeprefix('credit_')}"
    return PAYMENT_LABELS.get(method, method)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderArgs(_Args):
    order_id: int = Field(description="Número do pedido informado pelo cliente.")
    contact: str = Field(description="Telefone ou e-mail informado pelo cliente nesta conversa.")


class CustomerOrdersArgs(_Args):
    phone: str = Field(description="Telefone informado pelo cliente.")
    email: str = Field(description="E-mail informado pelo cliente.")


class ReturnArgs(OrderArgs):
    reason: Literal["arrependimento", "defeito", "troca_por_preferencia"]


class TicketArgs(_Args):
    kind: Literal["reclamacao", "atendimento_humano", "cancelamento", "outro"]
    summary: str = Field(description="Resumo objetivo do que o cliente relatou e do que precisa.")
    contact: str | None = Field(None, description="Telefone ou e-mail para retorno, se o cliente informou.")
    order_id: int | None = None


GUIDANCE = {
    (ReturnReason.REGRET, Outcome.ELIGIBLE): (
        "Dentro do prazo de arrependimento, que vale para compras online. Confirme que a compra foi online. "
        "Produto na embalagem original, sem uso, com acessórios e manuais. Frete de devolução por conta da loja. "
        "Reembolso na forma de pagamento original em até 10 dias úteis. Abra um ticket para a equipe seguir com a devolução."
    ),
    (ReturnReason.REGRET, Outcome.EXPIRED): (
        "Prazo de 7 dias corridos encerrado. Não presuma que a entrega atrasou: só ofereça conferência da equipe "
        "se o próprio cliente disser que recebeu bem depois da previsão. Se houver defeito, a regra é outra."
    ),
    (ReturnReason.PREFERENCE, Outcome.ELIGIBLE): (
        "Troca permitida se o produto desejado estiver disponível, em perfeito estado e na embalagem original. "
        "Diferenças de valor são cobradas ou reembolsadas. Abra um ticket para a equipe seguir com a troca."
    ),
    (ReturnReason.PREFERENCE, Outcome.EXPIRED): "Prazo de 7 dias para troca por preferência encerrado.",
    (ReturnReason.DEFECT, Outcome.ELIGIBLE): (
        "Dentro dos 30 dias para troca por defeito de fabricação. Mau uso, queda, umidade excessiva ou modificação "
        "não autorizada não têm cobertura. Abra um ticket para a equipe avaliar."
    ),
    (ReturnReason.DEFECT, Outcome.WARRANTY): (
        "Passou dos 30 dias para troca direta, mas a garantia legal de 90 dias segue válida. O caminho é o acionamento "
        "da garantia, e a loja pode intermediar junto ao fabricante. Mau uso e desgaste natural não têm cobertura. "
        "Ofereça abrir um ticket."
    ),
    (ReturnReason.DEFECT, Outcome.MANUFACTURER): (
        "Passaram a troca direta e a garantia legal. Resta a garantia do fabricante (de 6 meses a 2 anos, conforme o "
        "certificado), e a loja pode intermediar."
    ),
}
NOT_DELIVERED_GUIDANCE = (
    "O pedido ainda não foi entregue, então os prazos de devolução não começaram. O manual não trata de cancelamento "
    "antes da entrega: não prometa cancelamento e abra um ticket do tipo cancelamento se o cliente quiser desistir."
)
CANCELLED_GUIDANCE = "Este pedido já está cancelado: não há o que devolver."
ESTIMATE_NOTE = (
    "A base não registra a data real de recebimento: o prazo_limite conta da previsão de entrega. "
    "Avise o cliente disso ao citar a data."
)
DEFECT_DATES_NOTE = (
    "O prazo_limite da troca conta da data da compra. A garantia_legal_ate conta do recebimento, e a base só tem "
    "a previsão de entrega: avise o cliente disso ao citar a garantia."
)


def build_order_tools(
    repo: StoreRepository,
    orders: OrderService,
    tickets: TicketService,
    sessions: SessionStore,
    clock: Clock,
    provider: str,
) -> list[Tool]:
    def guarded(session_id: str, action: Callable[[], dict]) -> dict:
        """Aplica o limite de tentativas antes de qualquer acesso aos dados."""
        if sessions.failed_verifications(session_id) >= MAX_FAILED_VERIFICATIONS:
            return {"verificado": False, "bloqueado": True, "instrucao": LOCKED_MESSAGE}
        try:
            return {"verificado": True, **action()}
        except VerificationFailed:
            failures = sessions.record_failed_verification(session_id, provider)
            if failures >= MAX_FAILED_VERIFICATIONS:
                return {"verificado": False, "bloqueado": True, "instrucao": LOCKED_MESSAGE}
            return {
                "verificado": False,
                "instrucao": FAILED_MESSAGE,
                "tentativas_restantes": MAX_FAILED_VERIFICATIONS - failures,
            }

    def order_view(order: Order) -> dict:
        today = clock.now().date()
        items = [
            {"produto": repo.products[i.product_id].name, "quantidade": i.quantity}
            for i in repo.items_of(order.id)
        ]
        view = {
            "pedido": order.id,
            "compra_realizada_em": format_date(order.order_date),
            "status": STATUS_LABELS[order.status],
            "itens": items,
            "total": format_brl(order.total),
            "pagamento": _payment_label(order.payment_method),
        }
        if order.tracking_code:
            view["codigo_rastreio"] = order.tracking_code
            view["limite_dos_dados"] = SHIPPING_DATA_LIMIT
        if order.estimated_delivery:
            view["previsao_entrega"] = format_date(order.estimated_delivery)
        if order.notes:
            view["observacao"] = order.notes
        if order.status is OrderStatus.SHIPPED and order.estimated_delivery and order.estimated_delivery < today:
            view["atrasado"] = True
            view["dias_de_atraso"] = (today - order.estimated_delivery).days
        return view

    def get_order(args: OrderArgs, session_id: str) -> dict:
        def action() -> dict:
            verified = orders.verified_order(args.order_id, args.contact)
            return {"primeiro_nome": verified.customer.first_name, **order_view(verified.order)}

        return guarded(session_id, action)

    def list_customer_orders(args: CustomerOrdersArgs, session_id: str) -> dict:
        def action() -> dict:
            customer, found = orders.verified_customer_orders(args.phone, args.email)
            return {"primeiro_nome": customer.first_name, "pedidos": [order_view(o) for o in found]}

        return guarded(session_id, action)

    def eligibility_view(order: Order, result: Eligibility) -> dict:
        view = {
            "pedido": order.id,
            "motivo": result.reason.value,
            "resultado": result.outcome.value,
        }
        if result.outcome is Outcome.NOT_DELIVERED:
            view["orientacao"] = NOT_DELIVERED_GUIDANCE
        elif result.outcome is Outcome.CANCELLED:
            view["orientacao"] = CANCELLED_GUIDANCE
        else:
            view["orientacao"] = GUIDANCE[(result.reason, result.outcome)]
            view["aviso_sobre_datas"] = DEFECT_DATES_NOTE if result.reason is ReturnReason.DEFECT else ESTIMATE_NOTE
        if result.deadline:
            view["prazo_limite"] = format_date(result.deadline)
        if result.legal_warranty_until:
            view["garantia_legal_ate"] = format_date(result.legal_warranty_until)
        view["hoje"] = format_date(clock.now().date())
        view["itens_sem_troca"] = (
            "Instrumentos personalizados ou com ajuste sob encomenda, itens de liquidação com aviso de venda final "
            "e boquilhas de sopro."
        )
        return view

    def check_return(args: ReturnArgs, session_id: str) -> dict:
        def action() -> dict:
            verified = orders.verified_order(args.order_id, args.contact)
            result = check_eligibility(verified.order, ReturnReason(args.reason), clock.now().date())
            view = eligibility_view(verified.order, result)
            view["primeiro_nome"] = verified.customer.first_name
            return view

        return guarded(session_id, action)

    def open_ticket(args: TicketArgs, session_id: str) -> dict:
        ticket = tickets.open(
            session_id, args.kind, args.summary, clock.now(), contact=args.contact, order_id=args.order_id
        )
        payload = {"protocolo": ticket.protocol, "encaminhado": True}
        if args.kind == "reclamacao":
            payload["prazo_de_retorno"] = "24 horas úteis"
        else:
            payload["prazo_de_retorno"] = "A equipe retorna em horário de funcionamento; não há prazo definido no manual."
        return payload

    return [
        Tool(
            "get_order",
            "Consulta status, itens, rastreio e previsão de entrega de um pedido. Exige o número do pedido e o telefone "
            "ou e-mail informado pelo cliente. Nunca preencha o contato por suposição.",
            OrderArgs,
            get_order,
        ),
        Tool(
            "list_customer_orders",
            "Lista os pedidos de um cliente que não sabe o número. Exige telefone e e-mail informados pelo cliente.",
            CustomerOrdersArgs,
            list_customer_orders,
        ),
        Tool(
            "check_return_eligibility",
            "Calcula os prazos de devolução, troca e garantia de um pedido. Exige número do pedido, contato e motivo. "
            "Use em vez de calcular datas por conta própria.",
            ReturnArgs,
            check_return,
        ),
        Tool(
            "open_ticket",
            "Registra reclamação ou encaminhamento para a equipe e devolve um protocolo. Use para reclamações, pedidos "
            "de atendimento humano, cancelamentos, devoluções aprovadas e dúvidas que o manual não resolve.",
            TicketArgs,
            open_ticket,
        ),
    ]

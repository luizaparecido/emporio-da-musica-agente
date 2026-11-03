"""Correções explícitas para contradições internas do manual.

Ficam versionadas aqui, separadas do PDF, porque são suposições a validar com a loja.
"""

from __future__ import annotations

# §7 cita um WhatsApp diferente da capa e do §1.2, que coincidem entre si.
# O e-mail do §1.2 tem acento no domínio; a capa traz a versão sem acento.
TEXT_REPLACEMENTS = {
    "(67) 3321-4500": "(67) 3341-4444",
    "contato@empóriodamusica.com.br": "contato@emporiodamusica.com.br",
}

SECTION_NOTES = {
    "3": "Nota: a parcela mínima varia conforme o número de parcelas. Vale a regra da seção 3.1.",
    "3.1": "Nota: em 1x não há parcela mínima. Em 2x e 3x, a parcela mínima é de R$ 50,00.",
    "4.3": "Nota: o manual não define o início dos 7 dias; considera-se a data de recebimento.",
}


def apply_errata(section_id: str, text: str) -> str:
    for wrong, right in TEXT_REPLACEMENTS.items():
        text = text.replace(wrong, right)
    note = SECTION_NOTES.get(section_id)
    return f"{text}\n{note}" if note else text

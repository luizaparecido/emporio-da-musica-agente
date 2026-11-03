"""Transforma o manual em PDF em seções, usando a estrutura tipográfica do documento.

Títulos são identificados pela fonte (negrito de 14pt e 12pt), não só pelo texto:
o §7.2 tem uma lista "1. Saudação", "2. Entendimento" que um regex confundiria com capítulos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from emporio_agent.policies.errata import apply_errata

HEADING_SIZES = (14.0, 12.0)
HEADING_PATTERN = re.compile(r"^(\d{1,2}(?:\.\d{1,2})?)\.?\s+(.+)$")
RUNNING_HEADER_LIMIT = 50  # pontos a partir do topo
PAGE_FOOTER = re.compile(r"^Página \d+$")
COVER_PAGES = 1
CLOSING_LINE = re.compile(r"^Empório da Música — Sua música começa aqui|^Última atualização:")


@dataclass(frozen=True)
class PolicySection:
    id: str
    title: str
    text: str
    page: int

    @property
    def parent_id(self) -> str | None:
        return self.id.split(".")[0] if "." in self.id else None


def _table_to_markdown(rows: list[list[str | None]]) -> str:
    cells = [[(c or "").replace("\n", " ").strip() for c in row] for row in rows]
    header, *body = cells
    lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(lines)


def _is_heading(line: dict) -> re.Match[str] | None:
    first_char = line["chars"][0]
    if "Bold" not in first_char["fontname"] or round(first_char["size"], 1) not in HEADING_SIZES:
        return None
    return HEADING_PATTERN.match(line["text"].strip())


def _page_blocks(page) -> list[tuple[float, str, re.Match[str] | None]]:
    """Blocos da página na ordem de leitura: (posição, texto, título ou None)."""
    tables = page.find_tables()
    blocks: list[tuple[float, str, re.Match[str] | None]] = [
        (table.bbox[1], _table_to_markdown(table.extract()), None) for table in tables
    ]
    for line in page.extract_text_lines(return_chars=True):
        top, text = line["top"], line["text"].strip()
        inside_table = any(t.bbox[1] <= top <= t.bbox[3] for t in tables)
        if inside_table or top < RUNNING_HEADER_LIMIT or PAGE_FOOTER.match(text) or CLOSING_LINE.match(text):
            continue
        blocks.append((top, text, _is_heading(line)))
    return sorted(blocks, key=lambda block: block[0])


def _join_wrapped_lines(lines: list[str]) -> str:
    """Reúne linhas quebradas pelo PDF, sem unir itens de lista nem tabelas."""
    output: list[str] = []
    for line in lines:
        starts_block = line.startswith(("•", "|")) or re.match(r"^\d+\. ", line)
        previous_is_table = output and output[-1].startswith("|")
        ended_sentence = output and output[-1].endswith((".", ":")) and not output[-1].startswith("•")
        if output and not starts_block and not previous_is_table and not ended_sentence:
            output[-1] += " " + line
        else:
            output.append(line)
    return "\n".join(output)


def load_sections(pdf_path: Path) -> list[PolicySection]:
    sections: list[tuple[str, str, int, list[str]]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for number, page in enumerate(pdf.pages[COVER_PAGES:], start=COVER_PAGES + 1):
            for _, text, heading in _page_blocks(page):
                if heading:
                    sections.append((heading.group(1), heading.group(2), number, []))
                elif sections:
                    sections[-1][3].append(text)
    return [
        PolicySection(id=sid, title=title, text=apply_errata(sid, _join_wrapped_lines(lines)), page=page)
        for sid, title, page, lines in sections
    ]

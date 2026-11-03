"""Recuperação de políticas por sumário: o LLM escolhe a seção e recebe o texto inteiro.

Com 8 páginas, isso evita embeddings, download de modelo e regra cortada no meio de um
chunk. A interface permite trocar por busca vetorial se o corpus crescer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from emporio_agent.policies.ingest import PolicySection, load_sections

PDF_GLOB = "*.pdf"


class PolicyRetriever(Protocol):
    def table_of_contents(self) -> list[tuple[str, str]]: ...

    def get(self, section_ids: list[str]) -> list[PolicySection]: ...


class SectionRetriever:
    def __init__(self, sections: list[PolicySection]) -> None:
        self._sections = sections
        self._by_id = {s.id: s for s in sections}

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> "SectionRetriever":
        pdfs = sorted(data_dir.glob(PDF_GLOB))
        if not pdfs:
            raise FileNotFoundError(f"Manual de políticas não encontrado em {data_dir}")
        return cls(load_sections(pdfs[0]))

    def table_of_contents(self) -> list[tuple[str, str]]:
        return [(s.id, s.title) for s in self._sections]

    def get(self, section_ids: list[str]) -> list[PolicySection]:
        """Pedir um capítulo ("4") também traz as subseções ("4.1", "4.2"...), sem repetir."""
        selected: dict[str, PolicySection] = {}
        for wanted in section_ids:
            for section in self._sections:
                if section.id == wanted or section.parent_id == wanted:
                    selected[section.id] = section
        return list(selected.values())

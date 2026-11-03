from pathlib import Path

import pytest

from emporio_agent.policies.retriever import SectionRetriever

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def retriever():
    return SectionRetriever.from_data_dir(DATA_DIR)


def _text(retriever, section_id):
    return retriever.get([section_id])[0].text


def test_table_of_contents_has_real_sections_only(retriever):
    ids = [sid for sid, _ in retriever.table_of_contents()]
    assert ids == [
        "1", "1.1", "1.2", "2", "3", "3.1", "4", "4.1", "4.2", "4.3", "4.4", "5", "5.1", "5.2", "5.3",
        "6", "6.1", "6.2", "7", "7.1", "7.2", "7.3", "8", "8.1", "8.2", "8.3", "9", "10",
    ]


def test_numbered_list_is_not_mistaken_for_chapters(retriever):
    flow = _text(retriever, "7.2")
    assert "1. Saudação" in flow and "5. Fechamento" in flow


def test_section_spanning_two_pages_stays_whole(retriever):
    assert "Jadlog" in _text(retriever, "5.2")
    assert "recusar o recebimento" in _text(retriever, "5.2")


def test_list_crossing_page_break_stays_whole(retriever):
    assert "Cumprimento de obrigações legais" in _text(retriever, "9")


def test_tables_become_markdown(retriever):
    hours = _text(retriever, "2")
    assert "| Sábado | 09:00 às 13:00 |" in hours
    assert "| PAC (Correios) | 5 a 12 dias úteis | Sim | Incluído |" in _text(retriever, "5.2")


def test_running_header_and_footer_are_removed(retriever):
    for section in retriever.get([sid for sid, _ in retriever.table_of_contents()]):
        assert "Manual de Políticas e Procedimentos" not in section.text
        assert "Página " not in section.text


def test_errata_fixes_contradictions(retriever):
    assert "(67) 3341-4444" in _text(retriever, "7")
    assert "3321-4500" not in _text(retriever, "7")
    assert "contato@emporiodamusica.com.br" in _text(retriever, "1.2")
    assert "Vale a regra da seção 3.1" in _text(retriever, "3")


def test_chapter_includes_subsections_without_duplicates(retriever):
    ids = [s.id for s in retriever.get(["4", "4.1"])]
    assert ids == ["4", "4.1", "4.2", "4.3", "4.4"]


def test_unknown_section_returns_nothing(retriever):
    assert retriever.get(["99"]) == []

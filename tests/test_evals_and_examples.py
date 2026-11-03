"""Garante que a tooling de evals e exemplos funciona antes de gastar créditos."""


from emporio_agent.agent.factory import build_agent
from emporio_agent.config import PROJECT_ROOT, Settings
from evals.cases import CASES, Case
from evals.run import check, render_report, run_case
from scripts.generate_examples import build_scenarios, run_scenario
from tests.fakes import ScriptedLLM, call, final


def _settings(tmp_path, clock):
    return Settings("anthropic", "fake-1", "low", PROJECT_ROOT / "data", PROJECT_ROOT / "prompts", tmp_path / "x.sqlite3", clock)


def test_case_ids_are_unique():
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids))


def test_check_reports_each_kind_of_failure(tmp_path, clock, repo):
    agent = build_agent(_settings(tmp_path, clock), llm=ScriptedLLM([call("get_store_status"), final("Abrimos às 9h")]))
    case = Case(
        "x",
        ["?"],
        required_tools={"consult_policy"},
        forbidden_tools={"get_store_status"},
        must_contain=["13h"],
        must_contain_any=["sábado"],
        must_not_contain=["9h"],
    )
    result = run_case(agent, case, repo.customers[14])
    assert not result.passed and len(result.failures) == 5


def test_check_passes_when_rules_hold(tmp_path, clock, repo):
    agent = build_agent(_settings(tmp_path, clock), llm=ScriptedLLM([call("get_store_status"), final("Abrimos às 9h")]))
    case = Case("x", ["?"], required_tools={"get_store_status"}, must_contain=["9H"])
    assert run_case(agent, case, repo.customers[14]).passed


def test_eval_phone_placeholder_is_replaced(tmp_path, clock, repo):
    llm = ScriptedLLM([final("ok")])
    agent = build_agent(_settings(tmp_path, clock), llm=llm)
    run_case(agent, Case("x", ["Tel {phone_14}"]), repo.customers[14])
    assert repo.customers[14].phone_digits in llm.seen_messages[0][0]["content"]


def test_example_rendering_records_real_tool_calls(tmp_path, clock):
    scenario = build_scenarios("a", "b")[0]
    script = [call("search_products", category="Violões"), final("Resposta 1"), final("Resposta 2"), final("Resposta 3")]
    agent = build_agent(_settings(tmp_path, clock), llm=ScriptedLLM(script))
    text = run_scenario(agent, scenario, "fake", "m", "2026-03-25T10:30")
    assert "> Tool `search_products`" in text and "**Tom:** Resposta 3" in text


def test_there_are_five_example_scenarios():
    assert len(build_scenarios("a", "b")) == 5

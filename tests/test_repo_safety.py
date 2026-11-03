"""Impede que chaves sejam versionadas no template de configuração."""

import re

from emporio_agent.config import PROJECT_ROOT


def test_env_example_has_no_secret_values():
    content = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    values = re.findall(r"^\w*(?:KEY|TOKEN|SECRET)\w*[ \t]*=(.*)$", content, flags=re.MULTILINE)
    assert values and all(not v.strip() for v in values)

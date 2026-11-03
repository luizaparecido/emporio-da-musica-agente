"""Monta o agente a partir da configuração."""

from __future__ import annotations

from emporio_agent.agent.loop import Agent
from emporio_agent.agent.prompt import load_system_prompt
from emporio_agent.config import Settings
from emporio_agent.data.repository import StoreRepository
from emporio_agent.llm.base import LLMClient
from emporio_agent.llm.factory import build_llm
from emporio_agent.memory.store import SessionStore
from emporio_agent.policies.retriever import SectionRetriever
from emporio_agent.services.catalog import CatalogService
from emporio_agent.services.orders import OrderService
from emporio_agent.services.tickets import TicketService
from emporio_agent.tools.catalog_tools import build_catalog_tools
from emporio_agent.tools.order_tools import build_order_tools
from emporio_agent.tools.registry import ToolRegistry


def build_registry(settings: Settings, sessions: SessionStore, provider: str) -> ToolRegistry:
    repo = StoreRepository.from_csv(settings.data_dir)
    catalog_tools = build_catalog_tools(
        repo, CatalogService(repo), SectionRetriever.from_data_dir(settings.data_dir), settings.clock
    )
    order_tools = build_order_tools(
        repo, OrderService(repo), TicketService(settings.db_path), sessions, settings.clock, provider
    )
    return ToolRegistry(catalog_tools + order_tools)


def build_agent(settings: Settings, llm: LLMClient | None = None) -> Agent:
    llm = llm or build_llm(settings)
    sessions = SessionStore(settings.db_path)
    return Agent(
        llm=llm,
        tools=build_registry(settings, sessions, llm.provider),
        sessions=sessions,
        system_prompt=load_system_prompt(settings.prompts_dir),
        clock=settings.clock,
    )

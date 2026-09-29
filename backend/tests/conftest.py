from collections.abc import Callable, Iterator

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.container import build_container
from app.main import create_app
from app.models import Base
from app.providers.triage.base import TriageProvider
from app.providers.triage.simulated import SimulatedTriage


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "triage_provider": "simulated",
        "database_url": "sqlite://",
        "rate_limit_requests": 1000,
        "triage_retry_jitter_min_s": 0.0,
        "triage_retry_jitter_max_s": 0.0,
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def engine():
    # In-memory SQLite shared across threads. Tables are created here, in the test
    # harness only — the application itself never creates schema (Alembic does).
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def make_client(engine, redis_client) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def _make(provider: TriageProvider | None = None, **overrides: object) -> TestClient:
        settings = make_settings(**overrides)
        container = build_container(
            settings,
            engine=engine,
            redis_client=redis_client,
            provider=provider or SimulatedTriage(seed=42),
        )
        client = TestClient(create_app(settings, container))
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.close()


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


VALID = {
    "text": "Burst water main flooding Street 12 since fajr, water entering ground floors",
    "location": "Street 12, G-9/2, Islamabad",
    "reporter_contact": "0300-1234567",
}

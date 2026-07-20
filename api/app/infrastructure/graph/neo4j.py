"""Async Neo4j driver lifecycle."""

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.shared.config import get_settings

_driver: AsyncDriver | None = None


def get_neo4j() -> AsyncDriver:
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def check_neo4j() -> None:
    await get_neo4j().verify_connectivity()


async def close_neo4j() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
    _driver = None

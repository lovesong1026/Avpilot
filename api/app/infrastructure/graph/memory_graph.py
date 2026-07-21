"""User-scoped Neo4j repository for the four-layer memory provenance graph."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.infrastructure.graph.neo4j import get_neo4j


async def ensure_memory_graph_schema() -> None:
    queries = [
        "CREATE CONSTRAINT memory_source_key IF NOT EXISTS "
        "FOR (n:MemorySource) REQUIRE (n.user_id, n.id) IS UNIQUE",
        "CREATE CONSTRAINT memory_fragment_key IF NOT EXISTS "
        "FOR (n:MemoryFragment) REQUIRE (n.user_id, n.id) IS UNIQUE",
        "CREATE CONSTRAINT memory_statement_key IF NOT EXISTS "
        "FOR (n:Statement) REQUIRE (n.user_id, n.id) IS UNIQUE",
        "CREATE CONSTRAINT memory_entity_key IF NOT EXISTS "
        "FOR (n:Entity) REQUIRE (n.user_id, n.id) IS UNIQUE",
        "CREATE INDEX memory_entity_name IF NOT EXISTS "
        "FOR (n:Entity) ON (n.user_id, n.normalized_name)",
        "CREATE INDEX memory_statement_normalized IF NOT EXISTS "
        "FOR (n:Statement) ON (n.user_id, n.normalized_key)",
    ]
    async with get_neo4j().session() as session:
        for query in queries:
            await session.run(query)


class MemoryGraphRepository:
    async def existing_entities(self, user_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (e:Entity {user_id: $user_id})
        RETURN e.id AS id, e.name AS name, e.normalized_name AS normalized_name,
               e.entity_type AS entity_type, e.aliases AS aliases, e.embedding AS embedding
        """
        return await self._rows(query, user_id=user_id)

    async def existing_statements(self, user_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (s:Statement {user_id: $user_id})
        RETURN s.id AS id, s.normalized_key AS normalized_key,
               s.statement_type AS statement_type, s.event_time AS event_time,
               s.embedding AS embedding
        """
        return await self._rows(query, user_id=user_id)

    async def write_extraction(
        self,
        *,
        source: dict[str, Any],
        fragments: list[dict[str, Any]],
        entities: list[dict[str, Any]],
        statements: list[dict[str, Any]],
    ) -> None:
        query = """
        MERGE (src:MemorySource {user_id: $user_id, id: $source.id})
        SET src += $source
        WITH src
        UNWIND $fragments AS fragment
        MERGE (f:MemoryFragment {user_id: $user_id, id: fragment.id})
        SET f += fragment
        MERGE (src)-[:HAS_FRAGMENT]->(f)
        WITH src
        UNWIND $entities AS entity
        MERGE (e:Entity {user_id: $user_id, id: entity.id})
        ON CREATE SET e.created_at = entity.created_at, e.mention_count = 0
        SET e.name = entity.name,
            e.normalized_name = entity.normalized_name,
            e.entity_type = entity.entity_type,
            e.aliases = entity.aliases,
            e.embedding = coalesce(entity.embedding, e.embedding),
            e.updated_at = entity.updated_at,
            e.mention_count = coalesce(e.mention_count, 0) + entity.mention_increment
        WITH src
        UNWIND $statements AS statement
        MATCH (f:MemoryFragment {user_id: $user_id, id: statement.fragment_id})
        MERGE (s:Statement {user_id: $user_id, id: statement.id})
        ON CREATE SET s.created_at = statement.created_at
        SET s.text = statement.text,
            s.normalized_key = statement.normalized_key,
            s.statement_type = statement.statement_type,
            s.predicate = statement.predicate,
            s.event_time = statement.event_time,
            s.confidence = statement.confidence,
            s.embedding = coalesce(statement.embedding, s.embedding),
            s.updated_at = statement.updated_at
        MERGE (f)-[:SUPPORTS]->(s)
        WITH s, statement
        OPTIONAL MATCH (s)-[old:SUBJECT|OBJECT]->()
        DELETE old
        WITH DISTINCT s, statement
        MATCH (subject:Entity {user_id: $user_id, id: statement.subject_id})
        MATCH (object:Entity {user_id: $user_id, id: statement.object_id})
        MERGE (s)-[:SUBJECT]->(subject)
        MERGE (s)-[:OBJECT]->(object)
        MERGE (subject)-[r:RELATES_TO {predicate: statement.predicate}]->(object)
        SET r.statement_id = s.id, r.updated_at = statement.updated_at
        """
        await self._run(
            query,
            user_id=source["user_id"],
            source=source,
            fragments=fragments,
            entities=entities,
            statements=statements,
        )

    async def graph(self, user_id: str, limit: int = 300) -> dict[str, Any]:
        query = """
        MATCH (n {user_id: $user_id})
        WHERE n:MemorySource OR n:MemoryFragment OR n:Statement OR n:Entity
        WITH n LIMIT $limit
        OPTIONAL MATCH (n)-[r]->(m {user_id: $user_id})
        WHERE m:MemorySource OR m:MemoryFragment OR m:Statement OR m:Entity
        RETURN collect(DISTINCT {
          id: n.id, labels: labels(n), name: coalesce(n.name, n.text, n.raw_text, n.id),
          source_type: n.source_type, entity_type: n.entity_type,
          statement_type: n.statement_type, event_time: n.event_time,
          community_id: n.community_id
        }) AS nodes,
        collect(DISTINCT CASE WHEN r IS NULL THEN null ELSE {
          id: elementId(r), source: n.id, target: m.id, kind: type(r),
          label: coalesce(r.predicate, '')
        } END) AS edges
        """
        rows = await self._rows(query, user_id=user_id, limit=limit)
        if not rows:
            return {"nodes": [], "edges": [], "stats": {}}
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        for row in rows:
            for node in row.get("nodes") or []:
                if node and node.get("id"):
                    nodes[node["id"]] = node
            for edge in row.get("edges") or []:
                if edge and edge.get("id"):
                    edges[edge["id"]] = edge
        stats: defaultdict[str, int] = defaultdict(int)
        for node in nodes.values():
            stats[self._kind(node.get("labels") or [])] += 1
        return {"nodes": list(nodes.values()), "edges": list(edges.values()), "stats": dict(stats)}

    async def timeline(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        query = """
        MATCH (src:MemorySource {user_id: $user_id})-[:HAS_FRAGMENT]->
              (:MemoryFragment)-[:SUPPORTS]->(s:Statement)
        WITH s, head(collect(DISTINCT src)) AS src
        MATCH (s)-[:SUBJECT]->(subject:Entity)
        MATCH (s)-[:OBJECT]->(object:Entity)
        WHERE s.statement_type = 'event'
        RETURN DISTINCT s.id AS id, s.text AS statement, s.event_time AS event_time,
               subject.name AS subject, coalesce(s.predicate, '关联') AS predicate,
               object.name AS object,
               src.id AS source_id, s.created_at AS created_at
        ORDER BY coalesce(s.event_time, s.created_at) DESC
        LIMIT $limit
        """
        return await self._rows(query, user_id=user_id, limit=limit)

    async def searchable_statements(self, user_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (src:MemorySource {user_id: $user_id})-[:HAS_FRAGMENT]->
              (:MemoryFragment)-[:SUPPORTS]->(s:Statement)
        WITH s, head(collect(DISTINCT src)) AS src
        MATCH (s)-[:SUBJECT]->(subject:Entity)
        MATCH (s)-[:OBJECT]->(object:Entity)
        RETURN DISTINCT s.id AS id, s.text AS text, s.embedding AS embedding,
               s.statement_type AS statement_type, s.event_time AS event_time,
               coalesce(s.predicate, '关联') AS predicate,
               subject.name AS subject, object.name AS object, src.id AS source_id
        """
        return await self._rows(query, user_id=user_id)

    async def rebuild_communities(self, user_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (e:Entity {user_id: $user_id})
        OPTIONAL MATCH (e)-[:RELATES_TO]-(other:Entity {user_id: $user_id})
        RETURN e.id AS id, e.name AS name, collect(DISTINCT other.id) AS neighbors
        """
        rows = await self._rows(query, user_id=user_id)
        parent = {row["id"]: row["id"] for row in rows}

        def find(item: str) -> str:
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        def union(left: str, right: str) -> None:
            if right not in parent:
                return
            a, b = find(left), find(right)
            if a != b:
                parent[b] = a

        for row in rows:
            for neighbor in row["neighbors"]:
                union(row["id"], neighbor)
        groups: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            groups[find(row["id"])].append({"id": row["id"], "name": row["name"]})
        communities: list[dict[str, Any]] = []
        for index, members in enumerate(sorted(groups.values(), key=len, reverse=True), 1):
            community_id = f"community-{index}"
            name = " · ".join(item["name"] for item in members[:3])
            communities.append(
                {"id": community_id, "name": name, "member_count": len(members), "members": members}
            )
            await self._run(
                "MATCH (e:Entity {user_id: $user_id}) WHERE e.id IN $ids "
                "SET e.community_id = $community_id",
                user_id=user_id,
                ids=[item["id"] for item in members],
                community_id=community_id,
            )
        return communities

    async def prune_orphans(self, user_id: str) -> None:
        await self._run(
            "MATCH (e:Entity {user_id: $user_id}) "
            "WHERE NOT (:Statement)-[:SUBJECT|OBJECT]->(e) DETACH DELETE e",
            user_id=user_id,
        )

    async def delete_source(self, user_id: str, source_id: str) -> None:
        # Entities/statements can be shared by multiple sources after deduplication.
        query = """
        MATCH (src:MemorySource {user_id: $user_id, id: $source_id})
        OPTIONAL MATCH (src)-[:HAS_FRAGMENT]->(f:MemoryFragment)
        DETACH DELETE src, f
        WITH 1 AS ignored
        MATCH (s:Statement {user_id: $user_id})
        WHERE NOT (:MemoryFragment)-[:SUPPORTS]->(s)
        DETACH DELETE s
        WITH 1 AS ignored
        MATCH (e:Entity {user_id: $user_id})
        WHERE NOT (:Statement)-[:SUBJECT|OBJECT]->(e)
        DETACH DELETE e
        """
        await self._run(query, user_id=user_id, source_id=source_id)

    async def _rows(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        async with get_neo4j().session() as session:
            result = await session.run(query, **parameters)
            return [record.data() async for record in result]

    async def _run(self, query: str, **parameters: Any) -> None:
        async with get_neo4j().session() as session:
            result = await session.run(query, **parameters)
            await result.consume()

    @staticmethod
    def _kind(labels: list[str]) -> str:
        mapping = {
            "MemorySource": "source",
            "MemoryFragment": "fragment",
            "Statement": "statement",
            "Entity": "entity",
        }
        return next((mapping[label] for label in labels if label in mapping), "entity")

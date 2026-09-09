# """
# Thin wrapper around the Neo4j driver for writing persona graph data.
#
# Expects these environment variables (defaults match a local
# `docker run neo4j` setup — see README for the exact command):
#     NEO4J_URI       (default: bolt://localhost:7687)
#     NEO4J_USER      (default: neo4j)
#     NEO4J_PASSWORD  (required, no default)
# """
#
# import os
#
# from app.graph.schema import CONSTRAINTS
#
#
# class GraphClient:
#     def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None):
#         from neo4j import GraphDatabase
#
#         self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
#         self.user = user or os.environ.get("NEO4J_USER", "neo4j")
#         self.password = password or os.environ.get("NEO4J_PASSWORD")
#
#         if not self.password:
#             raise RuntimeError(
#                 "NEO4J_PASSWORD is not set. Export it before connecting, "
#                 "e.g. `export NEO4J_PASSWORD=your-password`"
#             )
#
#         self._driver = GraphDatabase.driver(
#             self.uri,
#             auth=(self.user, self.password),
#             keep_alive=True,
#             max_connection_lifetime=60,  # Recycles connections every 60s
#             max_connection_pool_size=50
#         )
#
#     def close(self) -> None:
#         self._driver.close()
#
#     def __enter__(self) -> "GraphClient":
#         return self
#
#     def __exit__(self, *exc_info) -> None:
#         self.close()
#
#     def verify_connectivity(self) -> None:
#         self._driver.verify_connectivity()
#
#     def ensure_constraints(self) -> None:
#         with self._driver.session() as session:
#             for statement in CONSTRAINTS:
#                 session.run(statement)
#
#     def upsert_person(self, name: str, is_persona: bool = False) -> None:
#         with self._driver.session() as session:
#             session.run(
#                 """
#                 MERGE (p:Person {name: $name})
#                 ON CREATE SET p.is_persona = $is_persona
#                 ON MATCH SET p.is_persona = p.is_persona OR $is_persona
#                 """,
#                 name=name,
#                 is_persona=is_persona,
#             )
#
#     def upsert_fact(self, fact_id: str, text: str, category: str, source_id: str, source_path: str, persona_name: str) -> None:
#         with self._driver.session() as session:
#             session.run(
#                 """
#                 MERGE (f:Fact {id: $fact_id})
#                 SET f.text = $text, f.category = $category,
#                     f.source_id = $source_id, f.source_path = $source_path
#                 WITH f
#                 MATCH (p:Person {name: $persona_name})
#                 MERGE (p)-[:KNOWS]->(f)
#                 """,
#                 fact_id=fact_id, text=text, category=category,
#                 source_id=source_id, source_path=source_path, persona_name=persona_name,
#             )
#
#     def upsert_opinion(self, opinion_id: str, text: str, topic: str, sentiment: str, source_id: str, source_path: str, persona_name: str) -> None:
#         with self._driver.session() as session:
#             session.run(
#                 """
#                 MERGE (o:Opinion {id: $opinion_id})
#                 SET o.text = $text, o.topic = $topic, o.sentiment = $sentiment,
#                     o.source_id = $source_id, o.source_path = $source_path
#                 WITH o
#                 MATCH (p:Person {name: $persona_name})
#                 MERGE (p)-[:BELIEVES]->(o)
#                 """,
#                 opinion_id=opinion_id, text=text, topic=topic, sentiment=sentiment,
#                 source_id=source_id, source_path=source_path, persona_name=persona_name,
#             )
#
#     def upsert_event(self, event_id: str, text: str, date: str, location: str, source_id: str, source_path: str, persona_name: str) -> None:
#         with self._driver.session() as session:
#             session.run(
#                 """
#                 MERGE (e:Event {id: $event_id})
#                 SET e.text = $text, e.date = $date, e.location = $location,
#                     e.source_id = $source_id, e.source_path = $source_path
#                 WITH e
#                 MATCH (p:Person {name: $persona_name})
#                 MERGE (p)-[:EXPERIENCED]->(e)
#                 """,
#                 event_id=event_id, text=text, date=date, location=location,
#                 source_id=source_id, source_path=source_path, persona_name=persona_name,
#             )
#
#     def upsert_relationship(self, persona_name: str, other_person: str, relation_type: str) -> None:
#         with self._driver.session() as session:
#             session.run(
#                 """
#                 MATCH (p:Person {name: $persona_name})
#                 MERGE (o:Person {name: $other_person})
#                 MERGE (p)-[r:RELATED_TO {type: $relation_type}]->(o)
#                 """,
#                 persona_name=persona_name, other_person=other_person, relation_type=relation_type,
#             )
#
#     def get_persona_profile(self, persona_name: str, limit_per_type: int = 40) -> dict:
#         """
#         Pull everything known about a persona: facts, opinions, events,
#         and relationships. Used to build the persona system prompt in
#         Step 5. Capped per-type via `limit_per_type` to keep prompts a
#         reasonable size as a persona's graph grows.
#         """
#         with self._driver.session() as session:
#             facts = session.run(
#                 """
#                 MATCH (p:Person {name: $name})-[:KNOWS]->(f:Fact)
#                 RETURN f.text AS text, f.category AS category
#                 LIMIT $limit
#                 """,
#                 name=persona_name, limit=limit_per_type,
#             ).data()
#
#             opinions = session.run(
#                 """
#                 MATCH (p:Person {name: $name})-[:BELIEVES]->(o:Opinion)
#                 RETURN o.text AS text, o.topic AS topic, o.sentiment AS sentiment
#                 LIMIT $limit
#                 """,
#                 name=persona_name, limit=limit_per_type,
#             ).data()
#
#             events = session.run(
#                 """
#                 MATCH (p:Person {name: $name})-[:EXPERIENCED]->(e:Event)
#                 RETURN e.text AS text, e.date AS date, e.location AS location
#                 LIMIT $limit
#                 """,
#                 name=persona_name, limit=limit_per_type,
#             ).data()
#
#             relationships = session.run(
#                 """
#                 MATCH (p:Person {name: $name})-[r:RELATED_TO]->(o:Person)
#                 RETURN o.name AS person, r.type AS relation_type
#                 LIMIT $limit
#                 """,
#                 name=persona_name, limit=limit_per_type,
#             ).data()
#
#         return {
#             "facts": facts,
#             "opinions": opinions,
#             "events": events,
#             "relationships": relationships,
#         }
#
#     def delete_persona_data(self, persona_name: str) -> None:
#         with self._driver.session() as session:
#             session.run(
#                 """
#                 MATCH (p:Person {name: $persona_name})
#                 OPTIONAL MATCH (p)-[:KNOWS]->(f:Fact)
#                 OPTIONAL MATCH (p)-[:BELIEVES]->(o:Opinion)
#                 OPTIONAL MATCH (p)-[:EXPERIENCED]->(e:Event)
#                 DETACH DELETE p, f, o, e
#                 """,
#                 persona_name=persona_name,
#             )

import os
from neo4j import GraphDatabase


class GraphClient:
    def __init__(self):
        self.uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.environ.get("NEO4J_USER", "neo4j")
        self.password = os.environ.get("NEO4J_PASSWORD", "password")

        # Keep-alive settings to prevent Aura from dropping connections during long LLM extractions
        self._driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
            keep_alive=True,
            max_connection_lifetime=60,
            max_connection_pool_size=50
        )

    def close(self):
        self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def verify_connectivity(self):
        self._driver.verify_connectivity()

    def delete_persona_data(self, persona_name: str) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MATCH (p:Person {name: $persona_name})
                OPTIONAL MATCH (p)-[:KNOWS]->(f:Fact)
                OPTIONAL MATCH (p)-[:BELIEVES]->(o:Opinion)
                OPTIONAL MATCH (p)-[:EXPERIENCED]->(e:Event)
                OPTIONAL MATCH (p)-[:EXHIBITS]->(t:Trait)
                DETACH DELETE p, f, o, e, t
                """,
                persona_name=persona_name,
            )

    def upsert_fact(self, persona_name: str, fact_data: dict) -> None:
        # Fact nodes are scoped by (text, owner) so two personas who happen
        # to share a similar fact never end up sharing the same node —
        # without this, persona B's KNOWS edge could point at a Fact node
        # that persona A's later write silently overwrote.
        with self._driver.session() as session:
            session.run(
                """
                MERGE (p:Person {name: $persona_name})
                MERGE (f:Fact {text: $text, owner: $persona_name})
                SET f.category = $category
                MERGE (p)-[:KNOWS]->(f)
                """,
                persona_name=persona_name,
                text=fact_data.get("text", ""),
                category=fact_data.get("category", "")
            )

    def upsert_opinion(self, persona_name: str, opinion_data: dict) -> None:
        # Scoped by (topic, text, owner) rather than topic alone — the old
        # topic-only key meant a second opinion on the same topic (even
        # for the same persona) would silently overwrite the first one's
        # text/sentiment instead of being stored alongside it.
        with self._driver.session() as session:
            session.run(
                """
                MERGE (p:Person {name: $persona_name})
                MERGE (o:Opinion {topic: $topic, text: $text, owner: $persona_name})
                SET o.sentiment = $sentiment
                MERGE (p)-[:BELIEVES]->(o)
                """,
                persona_name=persona_name,
                topic=opinion_data.get("topic", ""),
                sentiment=opinion_data.get("sentiment", ""),
                text=opinion_data.get("text", "")
            )

    def upsert_event(self, persona_name: str, event_data: dict) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (p:Person {name: $persona_name})
                MERGE (e:Event {text: $text, owner: $persona_name})
                SET e.date = $date, e.location = $location
                MERGE (p)-[:EXPERIENCED]->(e)
                """,
                persona_name=persona_name,
                text=event_data.get("text", ""),
                date=event_data.get("date", ""),
                location=event_data.get("location", "")
            )

    def upsert_relationship(self, persona_name: str, rel_data: dict) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (p1:Person {name: $persona_name})
                MERGE (p2:Person {name: $other_person})
                MERGE (p1)-[r:RELATED_TO]->(p2)
                SET r.type = $rel_type
                """,
                persona_name=persona_name,
                other_person=rel_data.get("person", ""),
                rel_type=rel_data.get("relation_type", "")
            )

    def upsert_trait(self, persona_name: str, trait_data: dict) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (p:Person {name: $persona_name})
                MERGE (t:Trait {trait: $trait, owner: $persona_name})
                MERGE (p)-[r:EXHIBITS]->(t)
                SET r.context = $context
                """,
                persona_name=persona_name,
                trait=trait_data.get("trait", ""),
                context=trait_data.get("context", "")
            )

    def get_persona_profile(self, persona_name: str) -> dict:
        profile = {"facts": [], "opinions": [], "events": [], "relationships": [], "traits": []}
        with self._driver.session() as session:
            facts_res = session.run(
                "MATCH (p:Person {name: $name})-[:KNOWS]->(f:Fact) RETURN f.category AS category, f.text AS text",
                name=persona_name)
            profile["facts"] = [{"category": rec["category"], "text": rec["text"]} for rec in facts_res]

            opinions_res = session.run(
                "MATCH (p:Person {name: $name})-[:BELIEVES]->(o:Opinion) RETURN o.topic AS topic, o.sentiment AS sentiment, o.text AS text",
                name=persona_name)
            profile["opinions"] = [{"topic": rec["topic"], "sentiment": rec["sentiment"], "text": rec["text"]} for rec
                                   in opinions_res]

            events_res = session.run(
                "MATCH (p:Person {name: $name})-[:EXPERIENCED]->(e:Event) RETURN e.date AS date, e.location AS location, e.text AS text",
                name=persona_name)
            profile["events"] = [{"date": rec["date"], "location": rec["location"], "text": rec["text"]} for rec in
                                 events_res]

            rels_res = session.run(
                "MATCH (p1:Person {name: $name})-[r:RELATED_TO]->(p2:Person) RETURN p2.name AS person, r.type AS relation_type",
                name=persona_name)
            profile["relationships"] = [{"person": rec["person"], "relation_type": rec["relation_type"]} for rec in
                                        rels_res]

            traits_res = session.run(
                "MATCH (p:Person {name: $name})-[r:EXHIBITS]->(t:Trait) RETURN t.trait AS trait, r.context AS context",
                name=persona_name)
            profile["traits"] = [{"trait": rec["trait"], "context": rec["context"]} for rec in traits_res]

        return profile
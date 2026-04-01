# -*- coding: utf-8 -*-
"""
RAG Engine v0.1 — Retrieval Augmented Generation for N.E.L.S.O.N
================================================================
Phase 1: TF-IDF similarity (no external deps, stdlib only)
Phase 2 (future): pgvector semantic search when >500 docs

Sources ingested:
  - Agent logs (TelegramBot/logs/*.log)  → JSON lines
  - Oracle conversations (oracle.db)     → SQLite
  - Skills (.agent/skills/*.md)          → Markdown
"""

import json
import math
import re
import sqlite3
import logging
from pathlib import Path
from collections import Counter

log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent

LOG_DIR = ROOT / "TelegramBot" / "logs"
SKILLS_DIR = ROOT / ".agent" / "skills"
ORACLE_DB = ROOT / "TelegramBot" / "memory" / "oracle.db"


class Document:
    """A single retrievable document chunk."""

    __slots__ = ("id", "text", "source", "meta", "tokens")

    def __init__(self, id: str, text: str, source: str, meta: dict = None):
        self.id = id
        self.text = text
        self.source = source   # 'log' | 'conversation' | 'skill'
        self.meta = meta or {}
        self.tokens = self._tokenize(text)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r'\b[a-zA-Z0-9_/→\-]{2,}\b', text.lower())


class RAGEngine:
    """
    TF-IDF based retrieval engine.
    Loads documents from agent logs, Oracle memory, and skill files.
    Returns ranked context chunks for Gemini prompt injection.
    """

    def __init__(self):
        self.docs: list[Document] = []
        self._idf_cache: dict = {}
        self._loaded = False

    # ── Ingestion ─────────────────────────────────────────────────────────

    def ingest_logs(self, max_lines: int = 500):
        """Load structured JSON logs from TelegramBot/logs/ folder."""
        if not LOG_DIR.exists():
            return
        count = 0
        for log_file in LOG_DIR.glob("*.log"):
            try:
                lines = log_file.read_text(encoding="utf-8",
                                           errors="ignore").splitlines()
                for line in lines[-max_lines:]:
                    try:
                        obj = json.loads(line)
                        self.docs.append(Document(
                            id=f"log_{log_file.stem}_{count}",
                            text=obj.get("msg", ""),
                            source="log",
                            meta={"agent": obj.get("agent"),
                                  "ts": obj.get("ts")}
                        ))
                        count += 1
                    except (json.JSONDecodeError, KeyError):
                        pass
            except Exception:
                pass
        log.debug("[RAG] Ingested %d log entries", count)

    def ingest_conversations(self, limit: int = 200):
        """Load recent Oracle conversations."""
        if not ORACLE_DB.exists():
            return
        count = 0
        try:
            with sqlite3.connect(ORACLE_DB) as c:
                rows = c.execute(
                    "SELECT id, user_id, role, content, ts "
                    "FROM conversations ORDER BY ts DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            for row in rows:
                self.docs.append(Document(
                    id=f"conv_{row[0]}",
                    text=row[3] or "",
                    source="conversation",
                    meta={"user_id": row[1], "role": row[2], "ts": row[4]}
                ))
                count += 1
        except Exception as e:
            log.warning("[RAG] Conversation ingest failed: %s", e)
        log.debug("[RAG] Ingested %d conversations", count)

    def ingest_skills(self, max_chars: int = 3000):
        """Load .agent/skills/ markdown files as knowledge documents."""
        if not SKILLS_DIR.exists():
            return
        count = 0
        for skill_dir in SKILLS_DIR.iterdir():
            if skill_dir.is_dir():
                md = skill_dir / "SKILL.md"
                if md.exists():
                    try:
                        text = md.read_text(encoding="utf-8",
                                            errors="ignore")[:max_chars]
                        self.docs.append(Document(
                            id=f"skill_{skill_dir.name}",
                            text=text,
                            source="skill",
                            meta={"skill_name": skill_dir.name}
                        ))
                        count += 1
                    except Exception:
                        pass
        log.debug("[RAG] Ingested %d skills", count)

    def ingest_all(self):
        """Load all sources and build IDF index."""
        self.docs.clear()
        self.ingest_logs()
        self.ingest_conversations()
        self.ingest_skills()
        self._build_idf()
        self._loaded = True
        log.info("[RAG] Corpus loaded: %d documents", len(self.docs))

    # ── TF-IDF retrieval ─────────────────────────────────────────────────

    def _build_idf(self):
        N = len(self.docs)
        if N == 0:
            return
        df = Counter()
        for doc in self.docs:
            for token in set(doc.tokens):
                df[token] += 1
        self._idf_cache = {
            t: math.log((N + 1) / (c + 1)) + 1
            for t, c in df.items()
        }

    def _score(self, query_tokens: list[str], doc: Document) -> float:
        if not self._idf_cache:
            return 0.0
        tf = Counter(doc.tokens)
        doc_len = max(len(doc.tokens), 1)
        score = 0.0
        for t in query_tokens:
            if t in tf and t in self._idf_cache:
                score += (tf[t] / doc_len) * self._idf_cache[t]
        return score

    def retrieve(self, query: str, top_k: int = 5,
                 source_filter: str = None) -> list[dict]:
        """
        Main retrieval method.
        Returns top_k most relevant document chunks.
        """
        if not self._loaded:
            self.ingest_all()

        q_tokens = Document._tokenize(query)
        scored = []
        for doc in self.docs:
            if source_filter and doc.source != source_filter:
                continue
            s = self._score(q_tokens, doc)
            if s > 0:
                scored.append((s, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "score": round(s, 4),
                "source": d.source,
                "text": d.text[:400],
                "meta": d.meta,
            }
            for s, d in scored[:top_k]
        ]

    def build_context_for_query(self, query: str) -> str:
        """
        Returns a compact context string to inject into Gemini prompt.
        Called by ai_chat.py before building the full message.
        """
        results = self.retrieve(query, top_k=3)
        if not results:
            return ""
        lines = ["[RAG Context — relevant system knowledge:]"]
        for r in results:
            src = r["source"]
            snippet = r["text"][:200].replace("\n", " ").strip()
            lines.append(f"  [{src}] {snippet}")
        return "\n".join(lines)


# ── Standalone test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")
    rag = RAGEngine()
    rag.ingest_all()
    print(f"\nDocs loaded: {len(rag.docs)}")

    test_queries = [
        "HPL rate HCM LAX freetime",
        "urgent booking PLAX26030654",
        "CMA vs ONE price comparison",
    ]
    for q in test_queries:
        print(f"\n=== Query: {q} ===")
        results = rag.retrieve(q, top_k=3)
        for r in results:
            print(f"  {r['source']} ({r['score']:.3f}): {r['text'][:80]}")

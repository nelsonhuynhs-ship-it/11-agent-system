# ============================================================
#  RAG ENGINE — N.E.L.S.O.N AI OS
#  google-genai SDK + ChromaDB local vector store
#  Model: gemini-embedding-001
#  Run: python rag_engine.py  (to index all)
# ============================================================
import os, sys
from pathlib import Path

# Config
WORKSPACE = Path(r"D:\NELSON\2. Areas\PricingSystem\Engine_test")
RAG_DB = WORKSPACE / ".agent" / "rag_db"

# Load API key from config.py
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    try:
        sys.path.insert(0, str(WORKSPACE / ".agent" / "agents"))
        import config as agent_config
        GEMINI_API_KEY = getattr(agent_config, "GEMINI_API_KEY", "")
    except Exception:
        pass

EMBED_MODEL = "models/gemini-embedding-2"


class RAGEngine:
    def __init__(self):
        from google import genai
        import chromadb

        self._client_genai = genai.Client(api_key=GEMINI_API_KEY)
        RAG_DB.mkdir(parents=True, exist_ok=True)
        self.chroma = chromadb.PersistentClient(path=str(RAG_DB))
        self.collection = self.chroma.get_or_create_collection(
            name="nelson_knowledge",
            metadata={"hnsw:space": "cosine"},
        )

    def get_embedding(self, text):
        """Get embedding via gemini-embedding-001."""
        result = self._client_genai.models.embed_content(
            model=EMBED_MODEL,
            contents=text[:8000],
        )
        return result.embeddings[0].values

    def chunk_text(self, text, name="", size=500, overlap=50):
        """Split text into word-based chunks."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), size - overlap):
            chunk = " ".join(words[i:i + size])
            if chunk:
                chunks.append(chunk)
        return chunks or [text[:2000]]

    def index_all(self):
        """Index everything: .md files, VBA, Python agents, rules."""
        docs, ids, metas = [], [], []

        # 1. ALL .md files under .agent\
        agent_dir = WORKSPACE / ".agent"
        if agent_dir.exists():
            for f in agent_dir.rglob("*.md"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    if len(content.strip()) < 10:
                        continue
                    chunks = self.chunk_text(content, f.name)
                    for i, chunk in enumerate(chunks):
                        rel = f.relative_to(agent_dir)
                        safe_id = str(rel).replace("\\", "_").replace("/", "_").replace(" ", "_")
                        docs.append(chunk)
                        ids.append(f"md_{safe_id}_{i}")
                        metas.append({"source": str(f), "type": "markdown"})
                except Exception as e:
                    print(f"  Skip md {f.name}: {e}")

        # 2. SKILL.md files from parent .agent\skills\
        parent_skills = WORKSPACE.parent / ".agent" / "skills"
        if parent_skills.exists():
            for f in parent_skills.rglob("SKILL.md"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    chunks = self.chunk_text(content, f.name)
                    for i, chunk in enumerate(chunks):
                        docs.append(chunk)
                        ids.append(f"skill_{f.parent.name}_{i}")
                        metas.append({"source": str(f), "type": "skill"})
                except Exception as e:
                    print(f"  Skip skill {f.name}: {e}")

        # 3. VBA modules under ERP\
        erp_dir = WORKSPACE / "ERP"
        if erp_dir.exists():
            for f in erp_dir.rglob("*.bas"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    docs.append(content[:2000])
                    ids.append(f"vba_{f.stem}")
                    metas.append({"source": str(f), "type": "vba"})
                except Exception as e:
                    print(f"  Skip VBA {f.name}: {e}")

        # 4. Python agents
        agents_dir = WORKSPACE / ".agent" / "agents"
        if agents_dir.exists():
            for f in agents_dir.glob("*.py"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    docs.append(content[:2000])
                    ids.append(f"py_{f.stem}")
                    metas.append({"source": str(f), "type": "python"})
                except Exception as e:
                    print(f"  Skip py {f.name}: {e}")

        # 5. booking_rules.json
        for rules_path in [
            WORKSPACE / "ERP" / "carrier_rules" / "booking_rules.json",
            WORKSPACE / "booking_rules.json",
        ]:
            if rules_path.exists():
                try:
                    docs.append(rules_path.read_text(encoding="utf-8"))
                    ids.append("booking_rules")
                    metas.append({"source": str(rules_path), "type": "rules"})
                except Exception:
                    pass
                break

        if not docs:
            print("No documents found to index.")
            return 0

        # Batch embed and upsert
        print(f"Indexing {len(docs)} documents...")
        batch_size = 10
        indexed = 0
        for i in range(0, len(docs), batch_size):
            batch_docs = docs[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            batch_metas = metas[i:i + batch_size]
            try:
                embeddings = [self.get_embedding(d) for d in batch_docs]
                self.collection.upsert(
                    documents=batch_docs,
                    embeddings=embeddings,
                    ids=batch_ids,
                    metadatas=batch_metas,
                )
                indexed += len(batch_docs)
                print(f"  Batch {i // batch_size + 1}: {len(batch_docs)} docs OK")
            except Exception as e:
                print(f"  Batch {i // batch_size + 1} error: {e}")

        print(f"RAG indexed {indexed}/{len(docs)} documents")
        return indexed

    def query(self, question, n=5):
        """Query the knowledge base."""
        embedding = self._client_genai.models.embed_content(
            model=EMBED_MODEL,
            contents=question,
        ).embeddings[0].values

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n,
        )
        return results["documents"][0] if results["documents"] else []

    def get_stats(self):
        """Get collection stats."""
        return {
            "total_docs": self.collection.count(),
            "db_path": str(RAG_DB),
        }


# Convenience functions
def index_all():
    rag = RAGEngine()
    return rag.index_all()


def query(question, n=5):
    rag = RAGEngine()
    return rag.query(question, n)


if __name__ == "__main__":
    rag = RAGEngine()
    count = rag.index_all()
    print(f"\nDone. {count} docs indexed.")
    stats = rag.get_stats()
    print(f"Stats: {stats}")

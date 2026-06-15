# CLAUDE.md — AI Agent Operating Guide for CaseMinds

Read this fully before touching any file in this repo.

## 1. What Is CaseMinds

CaseMinds is a GraphRAG-powered legal research assistant for independent lawyers
in India. It ingests Indian Supreme Court judgments, High Court orders, and
statutory acts (IPC, CPC, NI Act, etc.), models citation relationships as a
graph, and answers natural-language legal queries with grounded, verified
citations.

**Core invariant:** Every legal claim in an answer must be backed by a real
judgment or statute that exists in the corpus. The system must never confidently
cite a case that doesn't exist. Fabricated citations in legal contexts cause
direct professional harm.

## 2. Repo Map

```
caseminds/
├── CLAUDE.md               ← you are here
├── README.md
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATA_PIPELINE.md
│   ├── AGENTS.md
│   ├── EVALUATION.md
│   ├── TECH_STACK.md
│   ├── API_SPEC.md
│   ├── DATABASE_SCHEMA.md
│   └── DEPLOYMENT.md
├── services/
│   ├── ingestion/          # scrapers, parsers, citation extractor
│   ├── graph/              # NetworkX graph store, traversal
│   ├── retrieval/          # ChromaDB + BM25 hybrid search, reranker
│   ├── agents/             # LangGraph pipeline (4 agents)
│   │   ├── prompts/        # versioned prompt files
│   │   └── tools/          # tool definitions
│   ├── api/                # FastAPI app
│   └── eval/               # evaluation harness, golden datasets
├── data/
│   ├── raw/                # downloaded judgments (gitignored)
│   ├── processed/          # parsed JSON (gitignored)
│   ├── graph.pkl           # NetworkX graph (gitignored)
│   └── chroma/             # ChromaDB (gitignored)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── eval/
├── scripts/                # one-off: seed, migrate, benchmark
├── pyproject.toml
├── docker-compose.yml
├── render.yaml
├── Makefile
└── .env.example
```

## 3. Coding Standards

- **Python 3.12**, type hints everywhere, `mypy --strict` must pass.
- `ruff` + `black` (line length 100). Run `make lint` before committing.
- All LLM calls go through `services/agents/llm_client.py` — never call
  Anthropic/Groq SDK directly in agent code. This enforces cost logging,
  prompt versioning, and routing.
- All prompts live in `services/agents/prompts/` as `.txt` files with
  semantic version tags. Never hardcode prompt strings in agent code.
- Conventional Commits: `feat:`, `fix:`, `eval:`, `docs:`, `chore:`.

## 4. Critical Rules

1. **No citation without corpus verification.** The Verification Agent is a
   hard gate — BriefGeneration has no direct path that bypasses it.
2. **Overruled case detection is non-optional.** If a retrieved judgment is
   marked `is_overruled=True` in the graph, it must be flagged to the user,
   never presented as current good law.
3. **BM25 + dense hybrid is mandatory** for statute queries. "Section 138 NI
   Act" must be retrieved via exact-match BM25, not semantic drift.
4. **Never store raw judgment text in git** — corpus data is large and may have
   licensing constraints. Only store structured metadata + citation graph.

## 5. Definition of Done

- [ ] `make lint && make typecheck && make test` all pass
- [ ] New agent behavior has eval cases in `services/eval/datasets/`
- [ ] Citation accuracy eval (`make eval-citations`) shows no regression vs baseline
- [ ] API changes documented in `docs/API_SPEC.md`
- [ ] Schema changes have a migration script

## 6. First-Time Setup

```bash
cp .env.example .env.local
docker compose up -d        # SQLite volume + ChromaDB persist in ./data/
make install                # poetry install
make seed                   # downloads ~200 sample judgments, builds graph
make run                    # uvicorn on :8000
```

## 7. Read Order (new contributor)

1. `docs/PRD.md`
2. `docs/ARCHITECTURE.md`
3. `docs/AGENTS.md`
4. `docs/DATA_PIPELINE.md`
5. `docs/EVALUATION.md`

# Archon RAG + OpenSpec Integration Guide

**Project**: Artificial-Planeswalker

---

## Core Workflow: Research → Document → Execute

Every development task follows this three-stage process:

```
1. RESEARCH (Archon RAG + Web Search)
   ↓
2. DOCUMENT (OpenSpec Proposal - see openspec/AGENTS.md)
   ↓
3. EXECUTE (Implementation - see openspec/AGENTS.md)
```

---

## Stage 1: Research (Archon RAG)

**Use Archon RAG for technical research before creating proposals.**

```python
# Search Archon RAG (keep queries SHORT: 2-5 keywords)
mcp__archon__rag_get_available_sources()
mcp__archon__rag_search_knowledge_base(query="SQLAlchemy models", match_count=5)
mcp__archon__rag_search_code_examples(query="PydanticAI tools", match_count=3)
mcp__archon__rag_read_full_page(url="https://...")
```

### Searching Specific Documentation:
1. **Get sources** → `rag_get_available_sources()` - Returns list with id, title, url
2. **Find source ID** → Match to documentation (e.g., "PydanticAI docs" → "src_abc123")
3. **Search** → `rag_search_knowledge_base(query="agent tools", source_id="src_abc123")`

### Query Best Practices:
✅ **GOOD Queries** (concise, focused):
- `rag_search_knowledge_base(query="vector search pgvector")`
- `rag_search_code_examples(query="React useState")`
- `rag_search_knowledge_base(query="authentication JWT")`

❌ **BAD Queries** (too long, unfocused):
- `rag_search_knowledge_base(query="how to implement vector search with pgvector in PostgreSQL")`
- `rag_search_code_examples(query="React hooks useState useEffect useContext")`

**If Archon RAG doesn't have info:** Supplement with WebSearch/WebFetch

---

## Stages 2 & 3: Document & Execute (OpenSpec)

**For all OpenSpec workflow details, see `openspec/AGENTS.md`:**
- How to create change proposals
- Required files (proposal.md, design.md, spec.md, tasks.md)
- Validation process
- Implementation workflow
- Archiving completed changes

---

## Integration: Archon RAG → OpenSpec

**Research findings flow into OpenSpec proposals:**

1. **Research Phase**: Use Archon RAG to gather technical knowledge
2. **Document Phase**: Include research findings in OpenSpec proposal
   - Document sources in `proposal.md` (Research Summary section)
   - Include patterns and examples in `design.md` (Research Findings section)
3. **Execute Phase**: Implement following OpenSpec workflow

### Example Research → OpenSpec Flow:

```python
# 1. Research with Archon RAG
rag_get_available_sources()
results = rag_search_knowledge_base(query="async SQLAlchemy", source_id="src_123", match_count=5)
examples = rag_search_code_examples(query="PydanticAI agent", match_count=3)

# 2. Create OpenSpec proposal (see openspec/AGENTS.md for details)
# Include research findings in proposal.md and design.md:
# - List Archon RAG sources used
# - Document key findings and patterns
# - Reference code examples found
# - Base technical decisions on research
```

---

## Quick Checklist

### ☑️ For Every Development Task
- [ ] Research with Archon RAG (SHORT queries: 2-5 keywords)
- [ ] Document research sources and findings
- [ ] Follow OpenSpec workflow (see `openspec/AGENTS.md`)

---

## Critical Rules

### ✅ Always
1. Research with Archon RAG before creating proposals
2. Use short, focused queries (2-5 keywords) for RAG searches
3. Document research sources in OpenSpec proposals
4. Follow OpenSpec workflow in `openspec/AGENTS.md`

### ❌ Never
1. Skip Archon RAG research when available
2. Use long, unfocused queries for RAG searches
3. Create proposals without documenting research findings
4. Deviate from OpenSpec workflow without consulting `openspec/AGENTS.md`

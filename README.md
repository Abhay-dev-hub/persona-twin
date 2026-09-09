# Persona Twin

A chat app where the AI responds the way a specific person would —
tone, opinions, reactions — pulled from source material you feed it.

Built in stages (see `Persona_Twin.docx` for the full design):

1. Data extraction tool
2. Graph DB: persona knowledge graph (facts/opinions/relationships)
3. Chat UI + basic backend (no persona yet)
4. File/URL/image ingestion → chunk → embed → vector DB
5. Retrieval (vector + graph) + persona system prompt → generation ← you are here
6. Tune the persona prompt against real questions
7. Voice (optional add-on)

Stack: **FastAPI** backend, **Qdrant** (vector store), **Neo4j** (graph store), **OpenRouter** (LLM calls — image captioning + graph extraction + chat, model-agnostic).

## Step 1: Data extraction

Turns raw source material — documents, images, web pages — into
clean, chunked text, saved as JSONL. This is the input every later
step (embedding, graph extraction) builds on.

```
persona-twin/
├── app/
│   ├── cli.py                    # command-line entry point
│   └── ingestion/
│       ├── extract_files.py      # PDF, DOCX, TXT, MD
│       ├── extract_images.py     # vision-model captioning
│       ├── extract_urls.py       # fetch + main-content extraction
│       ├── chunker.py            # paragraph-aware chunking w/ overlap
│       └── pipeline.py           # ties extraction + chunking together
├── data/
│   ├── raw/                      # drop your source files here
│   └── output/                   # chunks.jsonl gets written here
├── requirements.txt
└── README.md
```

### Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your values — the CLI loads
it automatically, so you don't need to `export` anything manually or
re-set variables every time you open a new terminal:

```bash
cp .env.example .env    # Windows: copy .env.example .env
```

Then edit `.env` with a text editor and fill in `OPENROUTER_API_KEY`
(needed for image captioning) — Step 2 below covers the Neo4j values.

Image captioning calls an LLM via [OpenRouter](https://openrouter.ai),
so you'll need a key from there if you plan to feed in photos.

### Usage

Run everything from the `persona-twin/` directory:

```bash
# Extract one file (PDF, DOCX, TXT, MD, or an image — auto-detected)
python -m app.cli file data/raw/journal_entry.pdf

# Extract one URL
python -m app.cli url https://example.com/some-article

# Extract every supported file in a directory (recurses)
python -m app.cli dir data/raw

# Custom output path / chunk size
python -m app.cli dir data/raw --output data/output/my_chunks.jsonl --chunk-size 1000 --overlap 150
```

Each run appends to `data/output/chunks.jsonl`. Every line is one chunk:

```json
{
  "text": "...",
  "index": 0,
  "source_id": "c9f1d3a0-...",
  "source_type": "file",
  "source_path": "data/raw/journal_entry.pdf",
  "metadata": {}
}
```

That `source_id`/`source_type`/`source_path` trio is what Step 2 (the
persona knowledge graph) will use to link extracted facts back to
where they came from, and what Step 4's embedding step will use to
tag vectors in Qdrant.

### Notes

- **PDFs**: text-based PDFs only for now — scanned/image PDFs would need OCR (not included yet).
- **Images**: captioning requires `OPENROUTER_API_KEY`. Any vision-capable model on OpenRouter works — set `OPENROUTER_MODEL` to switch (e.g. `openai/gpt-4o`, `google/gemini-2.0-flash-001`).
- **URLs**: uses `trafilatura` for main-content extraction (strips nav/ads/boilerplate), with a plain-text fallback for pages it can't parse.
- `.env` is git-ignored by default (see `.gitignore`) — never commit your real one. `.env.example` is the safe template to share/commit instead.
- Chunking is paragraph-aware with configurable size/overlap, defaulting to 800 chars / 100 overlap — tune these once you see how retrieval quality looks in Step 4.

## Step 2: Persona knowledge graph

Reads `chunks.jsonl` (from Step 1), runs each chunk through an LLM to
pull out structured facts, opinions, events, and relationships, and
writes them into Neo4j as a graph centered on your persona.

```
app/graph/
├── schema.py         # node/relationship types + the extraction JSON schema
├── extractor.py       # calls Claude to extract structured data from a chunk
├── neo4j_client.py    # connection + upsert methods
└── pipeline.py         # ties it together: read chunks -> extract -> write
```

**Graph shape:**

```
(Person {name, is_persona})
  -[:KNOWS]->        (Fact {text, category, source_id, source_path})
  -[:BELIEVES]->      (Opinion {text, topic, sentiment, source_id, source_path})
  -[:EXPERIENCED]->   (Event {text, date, location, source_id, source_path})
  -[:RELATED_TO {type}]-> (Person)   # other people mentioned, e.g. "grandmother"
```

Every Fact/Opinion/Event keeps `source_id`/`source_path` from its
originating chunk, so anything the persona later says can be traced
back to the original source material.

### Setup

You need a running Neo4j instance. Easiest way locally, via Docker:

```bash
docker run -d --name persona-neo4j \
  -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/your-password-here \
  neo4j:5
```

No Docker? Neo4j also offers a free hosted instance ([Neo4j Aura](https://neo4j.com/product/auradb/)) — create one there instead, no local install needed.

Either way, fill in `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` in
your `.env` file (see Step 1 setup above for creating it) to match
whichever option you used:

```
NEO4J_URI=bolt://localhost:7687        # or neo4j+s://xxxx.databases.neo4j.io for Aura
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-here
```

### Usage

```bash
# Run Step 1 first if you haven't already, to produce chunks.jsonl
python -m app.cli dir data/raw

# Build the graph
python -m app.cli graph --persona "Jane Doe" data/output/chunks.jsonl
```

This prints progress per chunk and a summary count at the end. Browse
the resulting graph at `http://localhost:7474` (Neo4j Browser) if
running locally — try `MATCH (n) RETURN n LIMIT 100`.

### Notes

- Extraction is conservative by design — the prompt tells the model to only pull what's explicitly stated, not infer or embellish. If something important isn't showing up in the graph, it's worth checking the source chunk directly.
- Re-running `graph` on the same chunks is safe — facts/opinions/events are keyed by a fresh UUID each time (so re-running will duplicate them), but `Person` nodes and `RELATED_TO` relationships are deduplicated via `MERGE`. If you want a clean rebuild, drop the database first.
- `--model` lets you swap the extraction model if you want to trade cost/speed for quality.

## Step 3: Chat UI + FastAPI backend

A minimal chat interface talking to a FastAPI backend, both wired up
and working — but with no persona logic yet. This step is purely
about proving messages flow end to end (browser → API → OpenRouter →
back) before layering in retrieval and persona behavior in Step 5.

```
app/
├── main.py              # FastAPI app: /health, /api/chat, serves the UI
└── static/
    └── index.html         # plain HTML/JS chat interface, no framework
```

### Setup

Same `.env` as before — this step only needs `OPENROUTER_API_KEY`
(and optionally `OPENROUTER_MODEL`). Neo4j isn't touched yet.

### Usage

```bash
uvicorn app.main:app --reload
```

Then open **http://localhost:8000** in a browser and start chatting.

- `GET /health` — basic liveness check, returns `{"status": "ok"}`
- `POST /api/chat` — body: `{"message": "...", "history": [{"role": "user"|"assistant", "content": "..."}]}` → `{"reply": "..."}`
- `--reload` restarts the server automatically as you edit files, handy while developing

### Notes

- No persona, no retrieval, no memory beyond what the browser sends back each turn as `history` — this is intentionally bare-bones so Step 5 has a clean foundation to build persona behavior on top of.
- CORS is wide open (`allow_origins=["*"]`) for local development convenience. Tighten this before deploying anywhere public.
- Upstream OpenRouter failures (bad key, rate limits, etc.) surface as HTTP 502 with the underlying error message, rather than a raw crash.

## Step 4: Vector store (Qdrant)

Embeds every chunk from `chunks.jsonl` (Step 1) and stores the
vectors in Qdrant, so Step 5 can retrieve the most relevant chunks
for a given question instead of stuffing the whole persona's history
into every prompt.

```
app/vector/
├── embedder.py        # local embedding model (fastembed) — no API key, runs on CPU
├── qdrant_client.py    # connection + upsert/search methods
└── pipeline.py          # ties it together: read chunks -> embed -> upsert
```

Embeddings run **locally** via `fastembed` (default model:
`BAAI/bge-small-en-v1.5`, 384 dimensions) — no OpenRouter call, no
per-chunk cost, and it keeps working even if your OpenRouter key or
credits run out. The model downloads once on first use (a few hundred
MB) and is cached afterward.

### Setup

You need a running Qdrant instance. Easiest way locally, via Docker:

```bash
docker run -d --name persona-qdrant -p 6333:6333 qdrant/qdrant
```

No Docker? [Qdrant Cloud](https://cloud.qdrant.io) has a free tier — create a cluster there instead.

Fill in `QDRANT_URL` (and `QDRANT_API_KEY` if using Qdrant Cloud) in your `.env`:

```
QDRANT_URL=http://localhost:6333     # or your Qdrant Cloud cluster URL
QDRANT_API_KEY=                       # leave empty for local Qdrant
```

### Usage

```bash
# Embed and store (collection name is up to you — one per persona is a sane default)
python -m app.cli embed --collection jane_doe data/output/chunks.jsonl

# Try a search — this is the same retrieval step Step 5's chat will use internally
python -m app.cli search --collection jane_doe "what does she think about the ocean?"
```

`search` prints each matching chunk's similarity score, source file, and a text preview — useful for sanity-checking retrieval quality before wiring it into the chat flow.

### Notes

- Re-running `embed` on the same chunks appends duplicate points rather than deduplicating — if you want a clean rebuild after re-extracting, delete and recreate the collection (drop it in Qdrant's dashboard, or via `QdrantClient.delete_collection`).
- The 384-dim vector size is tied to the default embedding model. If you switch `EMBEDDING_MODEL` to something with a different output size, existing collections won't be compatible — start a fresh collection name.
- First run will be slower while the embedding model downloads; subsequent runs are fast and fully offline.

## Step 5: Persona-grounded chat

Ties Steps 2, 3, and 4 together: every chat message now triggers
retrieval from both Neo4j (the persona's facts/opinions/events/
relationships) and Qdrant (source chunks relevant to the question),
and the results get compiled into a system prompt that makes the
model respond *as* the persona — grounded in what was actually
extracted, not an improvised personality.

```
app/persona/
├── retrieval.py        # combines graph + vector lookups for a given question
└── prompt_builder.py   # turns retrieved context into a persona system prompt
```

### Setup

Add two more values to your `.env` — they tie the chat backend to the
persona and collection you already built in Steps 2 and 4:

```
PERSONA_NAME=Jane Doe
QDRANT_COLLECTION=jane_doe
```

These must match exactly what you used with `graph --persona` and
`embed --collection`, or retrieval will come back empty.

### Usage

Same as Step 3 — nothing changes about how you run it:

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000` and chat. Every message now:
1. Embeds your question and searches Qdrant for the most relevant source chunks
2. Pulls the persona's full fact/opinion/event/relationship profile from Neo4j
3. Builds a system prompt from both
4. Sends that + your message to the model

Check `GET /health` any time — it reports whether Neo4j and Qdrant are
actually reachable (`graph_connected`, `vector_connected`), separate
from whether a persona is configured at all (`persona_configured`).

### Notes

- **Degrades gracefully.** If Neo4j or Qdrant is down, or `PERSONA_NAME`/`QDRANT_COLLECTION` aren't set, the backend doesn't crash — it just responds with whatever context it *could* gather (or none at all, falling back to a plain assistant). Check `/health` if answers seem oddly generic.
- **Answer quality depends entirely on what's in the graph/vector store.** A persona built from a resume will sound like a resume — see the note in Step 4 about feeding in opinion-rich source material (journals, essays, posts) if you want a persona with an actual voice.
- The persona prompt explicitly tells the model not to invent facts, names, or events beyond what was retrieved — it's instructed to say "not sure" in-character rather than fabricate.
- Retrieval runs fresh on every message, based on that message's text alone (not the full conversation) — a very indirect follow-up question might retrieve less-relevant chunks than a self-contained one.

## Next up: Step 6

Tune the persona prompt against real questions — try it out, see where
tone or accuracy falls short, and refine the retrieval/prompt logic
based on what you find. Voice is an optional add-on after that.
## Deployment (100% Free on Render)

The application is fully containerized and configured to be deployed for free on [Render](https://render.com) using a free PostgreSQL database from [Neon.tech](https://neon.tech).

**1. Set up your Free Postgres Database (Chat History)**
By default, the app uses a local SQLite database, which is deleted on every restart in serverless/cloud environments. To fix this:
- Create a free account on [Neon.tech](https://neon.tech/).
- Create a new project and copy your **Postgres Connection String** (it starts with postgresql://).

**2. Push your code to GitHub**
Commit all your changes (including the Dockerfile and updated db.py) and push the repository to GitHub.

**3. Deploy to Render**
- Create a free account on [Render.com](https://render.com/).
- Click **New** -> **Web Service** -> **Build and deploy from a Git repository**.
- Connect your GitHub repo.
- In the deployment settings, make sure the Environment is set to **Docker**.
- Add the following **Environment Variables**:
  - DATABASE_URL: Your Neon.tech connection string
  - OPENROUTER_API_KEY: Your OpenRouter API key
  - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD: Your free Neo4j Aura credentials
  - QDRANT_URL, QDRANT_API_KEY: Your free Qdrant Cloud credentials

Click **Deploy**! Render will build your app and provide you with a live, persistent, and 100% free URL.

*(Note: Render's free tier spins down after 15 minutes of inactivity. When you open the app after it sleeps, it may take ~30 seconds to wake up).*

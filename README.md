# MenuElf | AI-Powered Restaurant Discovery for Calgary

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?logo=openai&logoColor=white)
![Leaflet](https://img.shields.io/badge/Leaflet-199900?logo=leaflet&logoColor=white)

Semantic search across **487 restaurants** and **18,000+ menu items**, powered by OpenAI embeddings and GPT-4o-mini.

**Live Demo** &rarr; [menuelf-production.up.railway.app/app](https://menuelf-production.up.railway.app/app)

---

## Features

**Semantic Dish Search.**
Natural language search across the entire Calgary restaurant database. Users type what they're craving — "spicy chicken under $15", "vegan pasta", "best dessert" — and get AI-ranked results with prices, dietary info, and restaurant names. Results can be filtered by price range, food category, and dietary restrictions.

**Interactive Restaurant Map.**
Browse all 487 restaurants on an interactive Leaflet map powered by OpenStreetMap. Hover over any pin to see ratings, review count, address, and a link to start a conversation about the menu.

**AI Menu Chat.**
Chat with GPT-4o-mini about any restaurant's complete menu. Ask about ingredients, spiciness levels, dietary restrictions, dish comparisons, pairing suggestions, and more. The AI has the full menu loaded in context, so every answer is grounded in real data.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  React Frontend                  │
│          Vite  ·  TypeScript  ·  Tailwind        │
│     Search UI  ·  Leaflet Map  ·  Chat Panel     │
└──────────────────────┬──────────────────────────┘
                       │  HTTP (JSON)
┌──────────────────────▼──────────────────────────┐
│                 FastAPI Backend                   │
│   /search-dishes   /restaurants   /chat           │
│                                                   │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ 487 Menu     │  │ OpenAI API               │  │
│  │ JSON Files   │  │  · text-embedding-3-large │  │
│  │ + Embeddings │  │  · GPT-4o-mini (chat)    │  │
│  └──────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Leaflet |
| Backend | FastAPI, Python 3.12, Uvicorn |
| AI / ML | OpenAI GPT-4o-mini, text-embedding-3-large, numpy |
| Data | 487 restaurant menus (JSON), semantic vector search |
| Deployment | Railway, Docker (multi-stage build) |

---

## How It Works

Restaurant menus were collected and structured into JSON with fields for dish name, price, description, category, and dietary info. All 18,000+ dishes are then embedded using OpenAI's `text-embedding-3-large` model (3072 dimensions), and the vectors are stored in a compressed numpy file.

When a user searches, their query is embedded with the same model and compared against every dish embedding using dot-product similarity. Results are ranked by semantic relevance, then filtered by price, category, and dietary restrictions on the server side. This means a query like "something warm and spicy" returns relevant curries and soups even if those exact words don't appear on the menu.

The chat feature works differently: it loads the selected restaurant's full menu JSON directly into GPT-4o-mini's context window. This gives the model complete, grounded knowledge of every dish, price, and ingredient, so it can answer detailed questions without hallucinating menu items.

---

## Project Structure

```
MenuElf/
├── web/                      React frontend (Vite + TypeScript)
│   └── src/
│       ├── components/       UI: search, map, chat, filters
│       ├── api.ts            Backend API client
│       └── types.ts          Shared TypeScript interfaces
├── backend/                  FastAPI server
│   ├── main.py               API endpoints + data loading
│   ├── menus/                487 restaurant menu JSONs
│   ├── menu_db.json          Flat dish index (18k items)
│   ├── menu_embeddings.npz   Precomputed dish embeddings
│   └── routers/              User intelligence, friends, groups
├── Dockerfile                Multi-stage build (Node + Python)
└── railway.toml              Railway deployment config
```

---

## Local Development

**1. Clone and set up the backend**

```bash
git clone https://github.com/alirezavafisani/MenuElf.git
cd MenuElf/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env` with your OpenAI key:

```
OPENAI_API_KEY=sk-...
```

Start the backend:

```bash
uvicorn main:app --reload --port 8000
```

**2. Start the frontend**

```bash
cd web
npm install
npm run dev
```

The dev server proxies API requests to `localhost:8000` automatically.

**3. Open the app**

Visit `http://localhost:5173` in your browser.

---

## Author

Built by [Alireza Vafisani](https://linkedin.com/in/alireza-vafisani) — Computer Science student at the University of Calgary.

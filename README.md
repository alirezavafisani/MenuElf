# MenuElf

**AI-powered restaurant and menu discovery for Calgary.**
Search across 487 restaurants and 18,000+ dishes using natural language. Ask the AI anything about any menu. Built with FastAPI, React, OpenAI embeddings, and GPT-4o-mini.

[Live Demo](https://menuelf-production.up.railway.app/app/)

## What it does

1. **Semantic dish search.** Type what you're craving ("spicy chicken under $15") and get the top 8 relevant dishes across all 487 Calgary restaurants, ranked by meaning not keywords.
2. **Hungry mode.** Click one button, get a random dish. Re-roll until something feels right. Optional budget cap.
3. **Visual category tiles.** 12 food categories with real photos. Tap to explore.
4. **AI menu chat.** Open any restaurant, ask anything about its menu. The AI has the full menu in context and will never make up dishes that aren't there.
5. **Interactive map.** Every restaurant as a pin. Tap for details.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Leaflet |
| Backend | FastAPI, Python 3.12 |
| AI | OpenAI text-embedding-3-large (semantic search), GPT-4o-mini (chat) |
| Data | 18,000+ menu items scraped from 487 Calgary restaurants, cleaned and embedded |
| Infra | Railway (Docker multi-stage build), Foursquare API (restaurant photos, scraped once), SQLite (privacy-preserving analytics) |

## How search works

Every dish is converted to a 3072-dimensional vector using OpenAI's embedding model. When a user searches, their query is embedded and compared against all dish vectors with cosine similarity. The top 8 matches are returned, filtered by price/category/dietary tags if specified.

## How the chat works

When a user opens a restaurant's chat, the full menu JSON is injected into the system prompt for GPT-4o-mini. The model is instructed to only recommend dishes that exist on the menu, include real prices, and never hallucinate. Rate limited to 30 messages per IP per hour.

## Privacy

MenuElf uses no cookies, no third-party analytics, no user accounts. Visitor counts use privacy-preserving daily-rotating IP hashes stored locally in SQLite. See `backend/analytics.py`.

## Local development

```bash
# Backend
cd backend
pip install -r requirements.txt
OPENAI_API_KEY=sk-... uvicorn main:app --reload

# Frontend
cd web
npm install
npm run dev
```

## Author

Built by [Alireza Vafisani](https://linkedin.com/in/alireza-vafisani), a CS student at the University of Calgary, because searching for Calgary restaurants shouldn't feel like homework.

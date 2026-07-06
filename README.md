# MenuElf

**Find the dish, not the restaurant.**
Search 18,000+ real menu items across 487 Calgary restaurants by what you're craving. Ask any menu a question. Built with FastAPI, React, OpenAI embeddings, and GPT-4o-mini.

[Live Demo](https://menuelf-production.up.railway.app/app/)

The idea: Google Maps already owns everything about the restaurant itself, the hours, photos, reviews and directions, and it does that better than any small app ever will. What it can't do is search structured menus with prices. So MenuElf owns the dish ("spicy chicken under $15, anywhere in Calgary") and hands everything else off to Google Maps with a deep link on every result. No rebuilt map, no stale copy of Google's data.

## What it does

1. **Semantic dish search.** Type what you're craving ("spicy chicken under $15") and get the top 8 relevant dishes across all 487 Calgary restaurants, ranked by meaning not keywords.
2. **AI menu chat.** Open any restaurant, ask anything about its menu. The AI has the full menu in context and will never make up dishes that aren't there.
3. **Distance and directions.** Share your location and results show how far each kitchen is, sortable closest first. One tap opens the restaurant in Google Maps for hours, reviews and directions.
4. **Hungry mode.** Click one button, get a random dish. Re-roll until something feels right. Optional budget cap.
5. **Visual category tiles.** 12 food categories with real photos. Tap to explore.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
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

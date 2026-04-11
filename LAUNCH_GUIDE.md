# MenuElf Launch Guide

## Pre-launch checklist

### Security
- [ ] OPENAI_API_KEY is in Railway env vars only, never in code or screenshots
- [ ] ANALYTICS_SALT is set in Railway env vars
- [ ] FOURSQUARE_API_KEY (if still present) is only in env vars
- [ ] No .env files committed to git
- [ ] Rate limiter on /chat is active (30 req/IP/hour)

### Data quality
- [ ] All 12 category tiles load images and return relevant results
- [ ] Hungry button only returns food (no drinks/wine)
- [ ] Chat responses are plain text, not markdown
- [ ] Search results capped at 8
- [ ] Map shows 487 pins

### Proof of use
- [ ] /stats endpoint returns real numbers
- [ ] Footer counter is visible and updating
- [ ] Take a screenshot of /stats JSON for your CV

## Launch day

### Screenshots to capture
1. Hero section ("Eat better tonight.")
2. Search results for something tasty (e.g. "spicy chicken under $15")
3. Hungry button with a good random dish
4. Chat conversation with a restaurant
5. Stats counter in footer
6. `/stats` JSON response

### Reddit post template
Target subreddits: r/Calgary, r/uofc (or r/ucalgary if that's the real name)

> Hey Calgary, I built a thing.
>
> It's called MenuElf. It's a website that lets you search across every menu at 487 Calgary restaurants using plain language ("spicy ramen under $15", "cheap vegan brunch", "best burger under $12"). You can also chat with an AI about any restaurant's menu and ask questions like "is the pad thai spicy" or "what's vegetarian" and it actually knows.
>
> I built it because I got tired of opening 10 tabs to decide where to eat. I'm a CS student at UofC and this is my side project.
>
> Link: https://menuelf.up.railway.app/app/
>
> Would love feedback, especially about:
> 1. Did the search actually find what you wanted?
> 2. Did the chat answer your questions correctly?
> 3. Any restaurants I'm missing that you love?
>
> No signup, no ads, no data collection. Just a tool.

### LinkedIn post template

> After 7 months, I'm launching MenuElf — an AI-powered restaurant discovery engine for Calgary.
>
> The problem: searching for food shouldn't feel like homework. Menu websites are ugly, Google shows outdated info, and asking "what's good here" means reading 50 reviews.
>
> What MenuElf does:
> - Semantic search across 487 Calgary restaurants and 18,000+ dishes ("spicy ramen under $15")
> - "Hungry" mode: click one button, get a random dish with a budget cap
> - AI chat for any restaurant's menu, grounded in real data so it never hallucinates
>
> Built with: FastAPI, React, OpenAI embeddings, GPT-4o-mini, Leaflet, Docker, Railway.
>
> Try it: https://menuelf.up.railway.app/app/
>
> No signup, no ads, no personalization. Just a tool for hungry Calgarians.
>
> Would love your feedback.

### After launch
- Check /stats once per day
- Reply to EVERY comment on the Reddit post within an hour
- If someone reports a bug, fix it same day and reply "fixed"
- After 2 weeks, screenshot /stats and add to CV

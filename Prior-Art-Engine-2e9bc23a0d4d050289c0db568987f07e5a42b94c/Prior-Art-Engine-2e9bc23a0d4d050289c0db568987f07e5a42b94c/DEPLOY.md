# Deploying to Render (free tier)

This deploys two services from one repo: `docket-backend` (FastAPI, Docker,
free web service) and `docket-frontend` (static site, free, served from the
built `frontend/dist`).

## ⚠️ Read this first: free-tier RAM risk

The backend loads two ML models into memory (`bge-small-en-v1.5` +
`ms-marco-MiniLM-L-6-v2`). Combined with torch's baseline overhead, that's
typically **600–900MB** at runtime. Render's free web service is capped at
**512MB**. I've minimized the footprint as much as is reasonable
(CPU-only torch, no GPU libs, models baked into the image rather than
loaded at request time), but there's a real chance the first search
request gets OOM-killed on a fresh deploy.

If that happens, you'll see the request hang then fail/timeout, and the
Render logs will show the instance restarting. Two ways out, in order of
preference:
1. **Upgrade only the backend** to Render's Starter plan (~$7/mo, 512MB →
   2GB depending on plan) — the frontend stays free either way.
2. Stay free, but accept slower/less reliable results — e.g. you could
   swap in a smaller pure-numpy similarity approach instead of the
   cross-encoder, though that changes the ranking quality (not done here,
   since you asked me not to change pipeline behavior).

It may also just work — 512MB is a soft target Render budgets for, and
short-lived inference spikes sometimes fit. Try it before assuming you
need to pay.

## Steps

### 1. Get a Gemini API key (optional but recommended)

ARM D and the Global Report need one. Get one free at
https://aistudio.google.com/apikey — without it, those two features
degrade gracefully and the rest of the app still works.

### 2. Push this project to GitHub

```bash
cd prior-art-engine
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

### 3. Deploy the Blueprint on Render

1. Go to https://dashboard.render.com → **New +** → **Blueprint**.
2. Connect your GitHub account and select the repo you just pushed.
3. Render detects `render.yaml` at the repo root and shows both services
   (`docket-backend`, `docket-frontend`) — click **Apply**.
4. Once `docket-backend` is created, open it → **Environment** → add:
   - `GEMINI_API_KEY` = your key from step 1
   (`CORS_ORIGINS` is already set in `render.yaml` to the frontend's
   predicted URL — see step 5 if the actual URL differs.)
5. Both services will build. The backend build takes the longest
   (~5–10 min — installing torch CPU + pre-downloading both models into
   the image). Watch the logs; if the build itself fails on memory/time,
   that's a separate, fixable problem from the runtime OOM risk above
   (Render's free build environment has more headroom than the free
   *runtime* instance).
6. Once both are live, note the actual URLs Render assigned
   (`https://docket-backend-xxxx.onrender.com`,
   `https://docket-frontend-xxxx.onrender.com` — Render appends a random
   suffix if your exact chosen name was taken). If they differ from the
   `render.yaml` defaults:
   - Update `docket-frontend`'s `VITE_API_BASE_URL` env var to
     `https://<actual-backend-url>/api`, then **Manual Deploy** to rebuild.
   - Update `docket-backend`'s `CORS_ORIGINS` env var to
     `https://<actual-frontend-url>`, then it'll restart automatically.

### 4. Test it

Open the frontend URL, paste a research idea, and submit. First request
after any idle period will be slow (~30–60s "cold start" — free instances
sleep after 15 minutes of inactivity and need to spin back up).

## Notes

- Free web services sleep after 15 min idle and cold-start on the next
  request — expect that delay after periods of no traffic.
- `CORS_ORIGINS` accepts a comma-separated list if you ever need to allow
  more than one frontend origin.
- If you outgrow free tier (reliability, no sleep, more RAM), the only
  change needed is switching `docket-backend`'s plan in the Render
  dashboard — no code changes required.

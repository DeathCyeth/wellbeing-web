# Getting Wellbeing Companion Online

Your app is set up for **all-in-one deployment**: the Flask server serves both the API and the frontend, so you only deploy one service.

---

## Option 1: Deploy to Render (recommended, free tier)

[Render](https://render.com) offers a free tier and works well with Flask + SQLite.

### 1. Put your code on GitHub

1. Create a new repository on [GitHub](https://github.com/new).
2. In your project folder, run:

   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git branch -M main
   git push -u origin main
   ```

   Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub username and repo name.

### 2. Create a Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com) and sign in (GitHub login is easiest).
2. Click **New** → **Web Service**.
3. Connect your GitHub account if needed, then select the **wellbeing-web** repository.
4. Configure the service:
   - **Name:** e.g. `wellbeing-companion`
   - **Region:** choose one close to you
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:**  
     `pip install -r requirements.txt`
   - **Start Command:**  
     `gunicorn --bind 0.0.0.0:$PORT server:app`
5. Click **Advanced** and add environment variables if you use AI features:
   - **Key:** `OPENAI_API_KEY`  
   - **Value:** your OpenAI API key (from [OpenAI](https://platform.openai.com/api-keys))
6. Click **Create Web Service**.

Render will build and deploy. When it’s done, you’ll get a URL like:

`https://wellbeing-companion.onrender.com`

Open that URL in your browser; the app and API will both be served from it.

### 3. Optional: custom domain

In your Render service → **Settings** → **Custom Domains**, add your own domain and follow the DNS instructions.

---

## Option 2: Deploy frontend and backend separately

If you prefer the frontend on one host and the backend on another:

1. **Backend:** Deploy `server.py` to Render (or Railway, Fly.io, etc.) as above, but **do not** use the “serve frontend” routes if you remove them; or keep them and use the same start command. Note the backend URL (e.g. `https://wellbeing-api.onrender.com`).
2. **Frontend:** Deploy the folder (e.g. to [Netlify](https://netlify.com) or [Vercel](https://vercel.com)) by dragging the folder or connecting the same repo and setting the publish directory to the project root.
3. **Point frontend at backend:** In `index.html`, add this before the script that loads `api-service.js`:

   ```html
   <script>window.API_BASE_URL = 'https://YOUR-BACKEND-URL.onrender.com/api';</script>
   ```

   Replace `YOUR-BACKEND-URL` with your actual Render (or other) backend URL.

---

## Notes

- **Free tier:** On Render’s free tier, the app may spin down after inactivity. The first request after that can take 30–60 seconds to wake up.
- **Why everyone needs new accounts after each deploy:** Accounts are stored in the **server** database, not only in the browser. With the default **SQLite** file (`wellbeing.db`) on Render (and many similar hosts), the container filesystem is **ephemeral** — each new deploy or fresh instance starts with an **empty** database. The app may still show an old name in the browser from `localStorage`, but login will fail until you register again. **Fix:** use a persistent database (recommended below).

### Persistent accounts (PostgreSQL — recommended)

1. In the Render dashboard, create a **PostgreSQL** instance (free or paid).
2. Copy its **Internal Database URL** (starts with `postgresql://`).
3. On your **Web** service → **Environment**, add:
   - **Key:** `DATABASE_URL`  
   - **Value:** the internal URL (Render often provides this automatically if you link the DB to the service).
4. Redeploy. The server already uses PostgreSQL when `DATABASE_URL` is set; tables are created on startup. Existing SQLite data on the server is not migrated automatically — register once after switching, or export/import manually if you need old rows.

### Persistent accounts (SQLite on a disk)

If you prefer SQLite, attach a **persistent disk** on Render, mount it (e.g. `/data`), and set:

- **Key:** `SQLITE_DATABASE_PATH`  
- **Value:** `/data/wellbeing.db` (must be on the mounted volume)

Without this, SQLite stays on ephemeral storage and is wiped on redeploy.

- **Health check:** `GET /api/health` returns `database` (`sqlite` or `postgresql`) and, for SQLite, `sqlite_path` so you can confirm where the file lives in logs.
- **AI features:** If you use the in-app AI, set `OPENAI_API_KEY` in the environment (e.g. in Render’s Environment tab). If it’s not set, the rest of the app still works; only AI endpoints will return an error.
- **Local testing:** You can still run everything locally with `python server.py` and open `http://localhost:8000`. The frontend will use `/api` on that same origin.

---

## Quick reference

| Task              | Command or action |
|-------------------|-------------------|
| Run locally      | `python server.py` then open http://localhost:8000 |
| Render start cmd | `gunicorn --bind 0.0.0.0:$PORT server:app` |
| Set API key      | Env var `OPENAI_API_KEY` in Render dashboard |

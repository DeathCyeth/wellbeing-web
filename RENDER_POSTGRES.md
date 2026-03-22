# Fix: accounts not saving long-term / cross-device login (PostgreSQL)

**"My account disappeared" or "I have to create the same account again"**  
On Render, the app stores accounts in a **SQLite file on the server’s disk**. That disk is **ephemeral**: when the service restarts or you redeploy, the container is recreated and the database file is **reset to empty**. So accounts don’t persist across redeploys or restarts. No code change “cleared” them—the container (and its SQLite file) was recreated.

**"Login works on my laptop but not on my tablet"**  
That can happen when each request hits a different instance (each with its own SQLite file) or when the DB was reset so the account no longer exists.

**Fix:** Use a **PostgreSQL database** on Render. The app already supports it: one shared, persistent database so accounts **save long-term** and work on **all devices**.

---

## Step 1: Add a PostgreSQL database on Render

1. In the [Render Dashboard](https://dashboard.render.com), click **New +** → **PostgreSQL**.
2. **Name:** e.g. `wellbeing-db`
3. **Region:** Choose the **same region** as your web service (e.g. Oregon).
4. **Plan:** Free or paid.
5. Click **Create Database**.
6. When it’s ready, open the database and copy the **Internal Database URL** (or **External** if your app will use it from outside Render). It looks like:
   `postgres://user:pass@host/dbname`

---

## Step 2: Connect your web service to the database

1. Open your **wellbeing-companion** (or your app) **Web Service**.
2. Go to **Environment**.
3. Click **Add Environment Variable**.
4. **Key:** `DATABASE_URL`
5. **Value:** paste the **Internal Database URL** from Step 1 (internal is better for services on Render).
6. Save. Render will redeploy your service.

---

## Step 3: Redeploy and test

After the deploy finishes:

1. **Create a new account** on the live site (from your laptop).
2. **Log out**.
3. Open the **same site URL** on your tablet and **log in** with that account.

The app now uses PostgreSQL. All devices and all instances use the same database, so the same account works everywhere.

---

## Check that you’re on the same server (optional)

On the login screen you’ll see something like:

**You're on: wellbeing-companion.onrender.com · Server: abc12def**

- If **Server:** is **different** on laptop vs tablet, requests are hitting different instances and each had its own SQLite DB. PostgreSQL fixes that.
- If **Server:** is the **same** and login still fails, check Render **Logs** for the line  
  `Login failed: username='...', user_exists=True/False`  
  to see whether the username exists or the password is wrong.

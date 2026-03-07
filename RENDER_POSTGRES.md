# Fix cross-device login: use one shared database (PostgreSQL)

If logging in works on one device (e.g. laptop) but not on another (e.g. tablet) **even with the same username and password**, the app is almost certainly using **different data** on each request. That happens when:

- Each Render instance has its own SQLite file, or
- The SQLite file is reset on redeploy/restart

**Fix:** Use a **single shared database** so every device and every request see the same users.

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

# Step-by-step: Paid deployment (Render)

Follow these steps in order. You’ll end up with your Wellbeing Companion app online, always on, with no spin-down.

---

## Part 1: Put your code on GitHub

### Step 1.1 – Create a GitHub account (if you don’t have one)

1. Go to [https://github.com](https://github.com).
2. Click **Sign up** and create an account.

### Step 1.2 – Create a new repository

1. Log in to GitHub.
2. Click the **+** icon (top right) → **New repository**.
3. **Repository name:** e.g. `wellbeing-web` (or any name you like).
4. Leave **Public** selected.
5. **Do not** tick “Add a README” (you already have code).
6. Click **Create repository**.

### Step 1.3 – Push your project from your computer

1. Open **PowerShell** (or Command Prompt).
2. Go to your project folder:
   ```powershell
   cd C:\Users\Jamie\Desktop\wellbeing-web
   ```
3. Run these commands one by one (replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub username and the repo name you chose in Step 1.2):

   ```powershell
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git branch -M main
   git push -u origin main
   ```

4. If Git asks you to log in, use your GitHub username and a **Personal Access Token** (not your password). To create one: GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Generate new token**; give it “repo” scope and paste it when Git asks for a password.

After this, your code should be on GitHub. You can refresh the repo page and see your files.

---

## Part 2: Create the app on Render

### Step 2.1 – Sign up / log in to Render

1. Go to [https://render.com](https://render.com).
2. Click **Get Started** (or **Log in** if you have an account).
3. Choose **Sign up with GitHub** and authorise Render to access your GitHub account.

### Step 2.2 – Create a new Web Service

1. In the Render dashboard, click **New +** (top right).
2. Click **Web Service**.
3. Under **Connect a repository**, find your **wellbeing-web** (or whatever you named it) repo and click **Connect** next to it.
   - If you don’t see it, click **Configure account** and allow Render to see the right GitHub org/user and repos, then try again.

### Step 2.3 – Configure the Web Service

Fill in the form exactly as below (you can change the name if you want):

| Field | Value |
|--------|--------|
| **Name** | `wellbeing-companion` (or any name; this becomes part of your URL) |
| **Region** | Choose the one closest to you (e.g. **Frankfurt** or **Oregon**) |
| **Branch** | `main` |
| **Runtime** | **Python 3** |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn --bind 0.0.0.0:$PORT server:app` |

Do **not** click **Create Web Service** yet.

### Step 2.4 – Add your OpenAI API key (optional but recommended for AI features)

1. In the same screen, scroll to **Environment** or **Environment Variables**.
2. Click **Add Environment Variable**.
3. **Key:** `OPENAI_API_KEY`
4. **Value:** your API key from [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys) (create one if you haven’t).
5. Leave **Secret** checked so it’s hidden.

### Step 2.5 – Create the service (still on free tier)

1. Scroll to the bottom.
2. Under **Instance Type**, leave **Free** selected for now.
3. Click **Create Web Service**.

Render will build and deploy. Wait until the status at the top shows **Live** (and the log says something like “Your service is live at …”). This can take a few minutes.

### Step 2.6 – Test the app

1. At the top of the page you’ll see something like: **Your service is live at `https://wellbeing-companion.onrender.com`** (your URL will match your service name).
2. Click that link and open it in your browser. You should see the Wellbeing Companion login page. Try logging in or creating an account to confirm it works.

---

## Part 3: Upgrade to a paid plan (always on, no spin-down)

### Step 3.1 – Open the plan / billing area

1. In the Render dashboard, make sure you’re in your **wellbeing-companion** service (click its name if needed).
2. In the left sidebar, click **Settings** (or the **Settings** tab at the top).

### Step 3.2 – Change instance type to paid

1. Scroll to the **Instance Type** section.
2. Click **Change** (or **Upgrade**).
3. Choose a **Starter** plan (e.g. **Starter – $7/month**). This gives you:
   - No spin-down (app stays on 24/7).
   - More memory and CPU.
   - Better for multiple users.
4. Confirm the change (e.g. **Save** or **Confirm**).

### Step 3.3 – Add a payment method (if Render asks)

1. If Render prompts you to add a payment method, go to **Account** (click your profile/avatar) → **Billing** or **Payment**.
2. Add a credit or debit card.
3. Return to your service; the instance type should now show **Starter** (or the plan you chose).

Your app is now on a paid plan: it will stay on, and the URL from Step 2.6 will keep working without long “waking up” delays.

---

## Part 4: Optional – Use your own domain

If you want a URL like `https://wellbeing.yourdomain.com`:

### Step 4.1 – Add the domain in Render

1. In your **wellbeing-companion** service, go to **Settings**.
2. Find **Custom Domains**.
3. Click **Add Custom Domain**.
4. Enter your domain (e.g. `wellbeing.yourdomain.com` or `yourdomain.com`).
5. Render will show you the exact DNS records to add (usually a **CNAME** or **A** record).

### Step 4.2 – Add the DNS record at your domain provider

1. Log in to where you bought your domain (e.g. GoDaddy, Namecheap, Google Domains, Cloudflare).
2. Open **DNS** or **DNS Management** for that domain.
3. Add the CNAME or A record exactly as Render shows (host/subdomain and target value).
4. Save. It can take a few minutes to 48 hours to propagate.

### Step 4.3 – Turn on HTTPS in Render

1. Back in Render → **Settings** → **Custom Domains**, wait until the domain shows as **Verified** or **Active**.
2. Render will issue an HTTPS certificate automatically; your app will then be available at `https://wellbeing.yourdomain.com`.

---

## Install on a phone (same app as the website)

There is **no “Download” button** in the App Store / Play Store for this version—it is a **website + PWA** you add from the browser.

### iPhone / iPad (Safari)

1. Open your live site in **Safari** (not Chrome-only tricks required on iOS).
2. Tap the **Share** icon (square with arrow).
3. Scroll and tap **Add to Home Screen**, then **Add**.

You get a home screen icon that opens the app full-screen, same data as the website.

### Android (Chrome)

1. Open the site in **Google Chrome** (if you opened the link inside Gmail, Facebook, etc., use **⋮ → Open in Chrome** first).
2. Tap **⋮** (menu) → **Install app** or **Add to Home screen** (wording varies by version).

### If you never see “Install”

- Confirm the latest code is deployed and visit **`https://YOUR-SERVICE.onrender.com/manifest.webmanifest`** — it should show JSON, not a 404.
- Same for **`/sw.js`** (JavaScript text).
- Use **HTTPS** (Render does by default).
- On **Android**, use **Google Chrome** (not Samsung Internet-only, and not the in-app browser inside Gmail/Facebook — use **Open in Chrome**).
- Manifest icons must be real **`pwa-icon-192.png`** and **`pwa-icon-512.png`** (fixed sizes). If you swap `logo.png`, run **`python scripts/generate_pwa_icons.py`** after `pip install Pillow` and redeploy — see **`LOGO_SETUP.md`**.

---

## Summary checklist

- [ ] Code pushed to GitHub (Part 1).
- [ ] Web Service created on Render with the correct **Build** and **Start** commands (Part 2).
- [ ] `OPENAI_API_KEY` added if you use AI features (Part 2.4).
- [ ] App tested via the Render URL (Part 2.6).
- [ ] Optional: phone install tested (Safari / Chrome “Add to Home screen” — see **Install on a phone** above).
- [ ] Instance type changed to **Starter** (or another paid plan) and payment method added if required (Part 3).
- [ ] Optional: custom domain added and DNS set (Part 4).

---

## Feedback email (Zapier → Gmail) troubleshooting

Emails only send **after** feedback is saved successfully (user must be logged in with a valid `feedback_token`, or Zap never runs).

1. **Render → Logs** after submitting feedback: search for **`FEEDBACK_NOTIFY_WEBHOOK`**.  
   - **`HTTP 4xx/5xx`**: the URL is wrong, revoked, or the receiver rejected the body (copy the log line).  
   - **`timed out`**: increase **`FEEDBACK_NOTIFY_WEBHOOK_TIMEOUT_SEC`** (default **25** seconds in newer server builds).

2. **Zapier → Zap history**: if there is **no run** when feedback is sent, the webhook URL on Render does not match the Zap’s Catch URL, or feedback never reached the server.

3. **Gmail step red / disconnected**: reconnect Google in Zapier; check **Spam**; map **Body** to **`feedback_body`** or **`message`** from step 1.

4. **Discord webhook URL** (if you use Discord instead of Zapier): Discord ignores Slack-style **`text`** alone — the server now also sends **`content`** for `discord.com/api/webhooks` URLs.

5. **SMTP path** (`FEEDBACK_EMAIL_*`): failures log as **`FEEDBACK email notify failed:`** — fix credentials or use Zapier only.

---

## If something goes wrong

- **Build fails:** Check the **Logs** tab on Render. Most often it’s a typo in **Build Command** or **Start Command**; compare with the table in Step 2.3.
- **“Application failed to respond”:** Wait 1–2 minutes after the first deploy; if it still fails, check the **Logs** for Python errors.
- **Login/API errors:** Make sure you’re opening the **Render URL** (e.g. `https://wellbeing-companion.onrender.com`), not `localhost`. The app is designed to use the same URL for the website and API when deployed.
- **Need help:** Render has a [documentation](https://render.com/docs) and [community forum](https://community.render.com); you can also contact their support if you’re on a paid plan.

Once you’ve finished Part 3, your site is online, always on, and ready for multiple users.

# AI web search & linkable sources

When enabled, the app runs a **live web search** for each AI chat question (and for nutrition-plan generation) and passes **real page titles, snippets, and URLs** into the model. The AI is instructed to use **only those URLs** when adding links in **Supporting references** (chat) or the **`references`** field (nutrition plan).

## How it works

- Uses **[Tavily](https://tavily.com)** (search API built for AI apps).
- No change is required to the frontend; everything is configured on the **server** with environment variables.

## Setup

### 1. Get a Tavily API key

1. Sign up at [https://tavily.com](https://tavily.com) (free tier available).
2. Create an API key from the dashboard.

### 2. Add the key to your environment

**Local (PowerShell):**

```powershell
$env:TAVILY_API_KEY="tvly-xxxxxxxx"
```

**Render (or other host):**

1. Open your **Web Service** → **Environment**.
2. Add variable:
   - **Key:** `TAVILY_API_KEY`
   - **Value:** your Tavily key
3. Save and redeploy.

### 3. Optional: turn search off without removing the key

Set:

```text
AI_WEB_SEARCH=0
```

(Default is on when `TAVILY_API_KEY` is set.)

## Behavior

| Feature | Web search |
|--------|------------|
| **Patient / Doctor AI chat** (`/api/ai/advice`) | Runs for each text question. **Skipped** when the message is image-only (vision). |
| **Nutrition plan** (`/api/ai/nutrition-plan`) | Runs a query based on patient context (e.g. diabetes, conditions, allergies). |

If `TAVILY_API_KEY` is **not** set, behavior is unchanged: citations stay as **named guidelines only** (no live URLs).

## Costs & limits

- Tavily has a **free tier** with monthly limits; check their site for current pricing.
- Each chat message triggers **one** search when the key is set.

## Privacy

- The **user’s question text** (and nutrition-plan search terms derived from patient fields) is sent to **Tavily** and their search providers. Use only where that is acceptable for your practice and policies.

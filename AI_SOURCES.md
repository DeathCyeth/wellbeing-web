# Where the AI gets its “sources” and how to edit them

## How it works today

Your app calls **OpenAI’s API** (`/api/ai/advice` and `/api/ai/nutrition-plan` in **`server.py`**). The model answers from its **training data** plus the **context you send** (patient preferences, doctor notes, medical fields you store in the app). It does **not** browse the web or read PDFs like some clinical tools.

So it is **not** the same as **DoxGPT-style** products that attach **specific documents** and cite **exact passages or links** from those documents. To get that behavior you would need **retrieval (RAG)**: upload/index guidelines, then pass retrieved chunks into the prompt with citations.

## Where to edit behavior and “tone” of sources

| What you want to change | File | Look for |
|-------------------------|------|----------|
| **Patient AI chat** (Wellbeing Companion) | `server.py` | `get_ai_advice` — the long `system_prompt` string for the patient (around “You are a helpful Wellbeing Companion”) |
| **Doctor AI assistant** | `server.py` | Same function — `system_prompt` when `role == 'doctor'` |
| **Nutrition plan JSON** (including `references`) | `server.py` | `generate_nutrition_plan` — the `prompt = f"""Generate a personalized nutrition plan...` block |
| Model / token limits | `server.py` | `client.chat.completions.create(...)` — `model`, `max_tokens`, `temperature` |

After editing, **restart** the server locally or **redeploy** on Render.

## Citations on every reply

`server.py` sends a **first system message on every API call** (`AI_CITATION_RULE_DOCTOR` / `AI_CITATION_RULE_PATIENT`) so **every** assistant answer—including short replies and follow-ups—must end with **`Supporting references`** (at least 2 bullets). Edit those constants near `get_ai_advice` to change wording or requirements.

## “Supporting references” (like DoxGPT *in spirit*)

The model is instructed to add a section:

- **`Supporting references`** (patient & doctor chat): short bullets naming **real guideline organizations or topic areas** (e.g. ADA, WHO, NHS). The model must **not** invent URLs or claim it opened a specific page.
- **`references`** (nutrition plan JSON): a string of named sources relevant to the plan.

These are **educational pointers** for users/clinicians to verify—not verified citations from your own document library.

## If you want true document-based citations later

You would need to:

1. Store guideline PDFs or pages in a **vector database** or search index.
2. On each question, **retrieve** the top matching chunks.
3. Put those chunks in the prompt and instruct the model to cite **chunk id / title / page** only from what you passed in.

That is a larger feature; the current app is **prompt + OpenAI only**.

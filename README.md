# Flask To-Do List (with schedule upload + progress pie chart)

## What it does
- Add tasks manually, defaulting due date to tomorrow.
- **Upload a schedule as a PDF or Word (.docx) file** — each line in the file
  becomes a task automatically (numbered lists like "1. Wake up" and bullets
  like "- Call mom" are cleaned up).
- Click **Done** to mark a task complete (click again to undo).
- A **pie chart** shows what % of tasks are complete vs. pending, updated live.

## Setup
```bash
cd todoapp
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser.

## How to use
1. Type a task and hit **Add**, or
2. Use the "Upload a schedule" box, choose a `.pdf` or `.docx` file with your
   daily plan (one task per line), pick the due date, and click
   **Generate tasks**.
3. Click **Done** on any task once you've finished it — the pie chart updates
   automatically.
4. Click **Delete** to remove a task.

## Notes
- Data is stored locally in `todo.db` (SQLite) — no external services needed.
- Uploaded files are saved in `uploads/` for reference.

## Deploying to Vercel

This repo includes `vercel.json` and `api/index.py` so it deploys as-is:

```bash
npm install -g vercel   # if you don't have the CLI yet
cd todoapp
vercel
```
Follow the prompts (link/create a project), then `vercel --prod` to go live.

**Important limitation:** Vercel's serverless filesystem is read-only except
for `/tmp`, and `/tmp` is wiped between cold starts and not shared across
instances. This app automatically switches its SQLite database to `/tmp` when
running on Vercel (detected via the `VERCEL` env var) so it won't crash — but
that also means **tasks can disappear** after a period of inactivity or when
Vercel spins up a new instance. It's fine for a quick demo, but not for real
day-to-day data.

For a todo list that actually remembers your tasks long-term, either:
- run this app on a host with a persistent disk (Render, Railway, Fly.io,
  PythonAnywhere, or your own server), or
- swap SQLite for a hosted database (e.g. Vercel Postgres, Supabase, Neon) —
  ask me and I can wire that up instead.


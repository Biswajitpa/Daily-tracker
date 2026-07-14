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

# aQui con fe Studio v2 — the Constellation

A private, self-hosted writing studio built as a **living archive / creative
ecosystem**: Questions sit at the center, and everything — materials, projects,
journal entries, references, room pieces — links to questions, to constellation
axes, and to projects. A philosophy expressed as software.

Single-user. Python 3 + Flask + SQLite. Server-rendered, no build step, no npm.

## The constellation

Eight axes, flowing QUESTION → MEMORY → STUDY → CRAFT → CREACIÓN → NEW MATERIAL → NEW QUESTION:

| Axis | Tagline |
|------|---------|
| Fe | the ground of belief |
| Aquí | here, in this place |
| Memoria | what the archive keeps |
| Letras | the word, written and read |
| Sonido | what is heard and sung |
| Arte | what the hand makes |
| Estudio | the discipline of inquiry |
| Creación | what is born from the rest |

## What's inside

- **Questions** — the center. Each question carries "Why am I asking?" and links
  to related areas. The dashboard surfaces **THE QUESTION**, rotating daily.
- **Materials** — poems, stories, essays, notes, fragments.
- **Projects** — the long works.
- **References** — books, films, songs, scripture, articles (private to the studio).
- **Journal** — dated entries of every kind.
- **Rooms** — OMG! moments, the aQui con fe video diary, coMe for Me, each with
  its own identity and piece structure.
- **Voice** — the house, out loud. Readings, conversations, interviews, audio
  notes, live sessions, podcast episodes — each with a script, an audio link,
  a transcript, and a shape from *idea* to *published*.
- **Serial** — a story in installments. Numbered chapters with arrival dates,
  written toward the every-two-weeks rhythm.
- **Newsletter** — letters to the ones who stay. Monthly letters, drafted
  gently, sent when ready.
- **Connections** — every item links to questions, axes, and (for materials) projects.
- **Public constellation** (`/constellation/`, no login) — the eight axes as
  dynamic cards, axis pages, and follow-the-question trails. Only items flagged
  **public** appear.
- **Publish** — one click renders the public constellation to static HTML under
  `export/constellation/`, ready to drop into the aquiconfe.org repo.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 — on first run you'll create a password.
Your writing lives in `./data/studio.db` (created automatically).
The eight axes, the three rooms, and a featured seed question
("What do we inherit that we did not choose?") are seeded on first run.

Environment variables (all optional):

| Variable            | Default                | What it does                        |
|---------------------|------------------------|-------------------------------------|
| `PORT`              | `5000`                 | Port to listen on                   |
| `STUDIO_DATA_DIR`   | `./data`               | Directory for the database + secret key |
| `STUDIO_DB`         | `<data dir>/studio.db` | Full path to the SQLite file        |
| `STUDIO_SECRET_KEY` | generated + saved in data dir | Flask session secret         |

## Deploy on PythonAnywhere (recommended — free, keeps your writing)

1. Create a free **Beginner** account at pythonanywhere.com.
2. Open a **Bash** console and clone this repo:
   `git clone https://github.com/<you>/aqui-con-fe-studio-v2.git`
3. Create a virtualenv and install: `pip install -r requirements.txt`
4. In the **Web** tab, create a new app (Manual configuration, Python 3.11),
   point its WSGI file at this folder's `app.py` (`from app import app as application`),
   and set the working directory to the repo folder.
5. Set `STUDIO_DATA_DIR` to a persistent path (e.g. `/home/<you>/.studio-data`)
   in the WSGI file via `os.environ`, reload, and create your password.

## Deploy on Render

1. Push this folder to a GitHub repo.
2. In Render: **New → Blueprint** and point it at the repo
   (`render.yaml` is included; it attaches a persistent disk so the SQLite
   database survives redeploys — required, since Render's free ephemeral
   storage would wipe your writing).
3. Open the app URL and create your password.

## Publishing the public constellation

In the studio, open **Publish** and click the button. Copy the generated
`export/constellation/` folder into the aquiconfe.org repo (next to
`index.html`), link to `/constellation/` from the homepage, commit, and push.
See `export/constellation/PUBLISH_README.txt` after publishing.

## Back up your writing

Everything lives in one file: the SQLite database (`./data/studio.db`
locally). Copy it somewhere safe regularly. To restore, put it back and
restart the app.

## Notes

- Keep the app URL private — anyone with the link reaches the login page,
  and the password is the only gate. Use a strong, unique password.
- The schema is created automatically on startup; axes, rooms, and the seed
  question are inserted idempotently.

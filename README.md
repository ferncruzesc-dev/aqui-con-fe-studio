# aQui con fe Studio

A private, self-hosted writing desk for the aQui con fe content hub —
Journal, Archive (collections + pieces), and drafting rooms for
OMG! moments, the aQui con fe video diary, and coMe for Me.

Single-user. Python 3 + Flask + SQLite. No build step, no npm.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 — on first run you'll create a password.
Your writing lives in `./data/studio.db` (created automatically).

Environment variables (all optional):

| Variable           | Default              | What it does                              |
|------------------|----------------------|-------------------------------------------|
| `PORT`           | `5000`               | Port to listen on                         |
| `STUDIO_DATA_DIR`| `./data`             | Directory for the database + secret key   |
| `STUDIO_DB`      | `<data dir>/studio.db` | Full path to the SQLite file            |
| `STUDIO_SECRET_KEY` | generated + saved in data dir | Flask session secret            |

## Deploy on Render

1. Push this folder to a GitHub repo.
2. In Render: **New → Blueprint** and point it at the repo
   (`render.yaml` is included).
3. Render generates `STUDIO_SECRET_KEY` and attaches a 1 GB persistent
   disk at `/var/studio-data`, so your writing survives redeploys.
4. Open the app URL and create your password.

## Deploy on Railway

1. Push this folder to a GitHub repo.
2. In Railway: **New Project → Deploy from GitHub**, select the repo.
   Railway reads the `Procfile` automatically.
3. Add a **Volume** to the service, mount path `/data`.
4. In **Variables**, set:
   - `STUDIO_DATA_DIR` = `/data`
   - `STUDIO_SECRET_KEY` = a long random string (generate one locally with
     `python -c "import secrets; print(secrets.token_hex(32))"`)
5. Deploy, open the app URL, create your password.

## Back up your writing

Everything lives in one file: the SQLite database
(`./data/studio.db` locally, or `/var/studio-data/studio.db` on Render,
`/data/studio.db` on Railway).

- **Local:** copy `data/studio.db` somewhere safe.
- **Render:** use the Shell tab → `cp /var/studio-data/studio.db /tmp/`
  then download it, or take a disk snapshot.
- **Railway:** open a shell on the service and copy `/data/studio.db` out.

To restore, put the file back at the same path and restart the app.

## Notes

- Keep the app URL private — anyone with the link reaches the login page,
  and the password is the only gate. Use a strong, unique password.
- The schema is created automatically on startup; future versions should
  migrate rather than recreate.

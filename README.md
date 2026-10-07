# Revelio

Web app for storing and accessing short links anonymously. Create a short key for a long URL, share it, and view or manage it later with its private admin key. No account needed.

Optionally, create an account (username and password; email only for password recovery) to keep your links in one place: links created while logged in can be saved to the account, then listed, revealed and deleted from the account page.

Built with FastAPI, SQLAlchemy, Jinja2 templates and htmx.

## Requirements

- Python 3.12

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root (the folder containing `requirements.txt`) with your settings:

```dotenv
ENV_NAME="Development"
BASE_URL="http://127.0.0.1:8000"
DB_URL="sqlite:///./shortener.db"
SECRET_KEY="<random string, see below>"
```

| Variable | Meaning |
|---|---|
| `ENV_NAME` | Name of the environment, printed on startup |
| `BASE_URL` | Public address of the app, used to build the short links |
| `DB_URL` | SQLAlchemy database URL. The SQLite file is created automatically on first run |
| `SECRET_KEY` | Signs the login session cookie. Anyone who knows it can forge logins, so keep it secret; changing it logs everyone out |

Generate a `SECRET_KEY` with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

The `.env` file is not committed to git. If it's missing, the app falls back to development defaults, including an insecure `SECRET_KEY` that must not be used in production.

## Running locally

From the project root:

```bash
uvicorn shortener_app.main:app --reload
```

`--reload` restarts the server when you change Python files. Stop it with `Ctrl+C`.

Database tables are created on startup, but existing tables are not changed. After a change to the models, delete `shortener.db` (this removes all data) so it's recreated with the new columns.

## Endpoints

| Method | Path | Type | Description |
|---|---|---|---|
| GET | `/` | Page | Home |
| GET | `/create_url` | Page | Create a short key; logged-in users can link it to their account |
| GET | `/go` | Page | Go to a link by its key |
| GET | `/manage` | Page | View or delete a link with its admin key |
| GET | `/account` | Page | Log in / create account, or, when logged in, the account with its links |
| GET | `/{url_key}` | Redirect | Redirects to the target URL and counts the click |
| POST | `/create_url/form` | htmx fragment | Creates a short key from the form on `/create_url` |
| GET | `/go/lookup?key=…` | htmx fragment | Checks a key and shows its target URL, without counting a click |
| POST | `/manage_key/form` | htmx fragment | Shows a link's details for an admin key |
| DELETE | `/manage_key/form` | htmx fragment | Deletes (deactivates) the link for an admin key, sent as form data |
| POST | `/sign_up` | htmx form | Creates an account and logs in |
| POST | `/login` | htmx form | Logs in |
| POST | `/logout` | Form | Logs out and redirects to `/account` |
| DELETE | `/account/links/{url_key}` | htmx | Deletes (deactivates) one of the logged-in user's own links |
| POST | `/create_url` | JSON API | Creates a short key (body: `{"target_url": "..."}`) |
| GET | `/manage_key/{secret_key}` | JSON API | Returns a link's details for an admin key |
| DELETE | `/manage_key_delete/{secret_key}` | JSON API | Deletes (deactivates) a link |
| GET | `/docs` | Docs | Interactive API documentation (Swagger UI) |

Deleting is a soft delete: the link is marked inactive, so its short link and admin key stop working, but the row stays in the database.

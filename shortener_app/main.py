from typing import Annotated
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from starlette.datastructures import URL
from pydantic import ValidationError

from sqlalchemy.orm import Session

from . import models, schemas, crud, keygen
from .database import SessionLocal, engine
from .config import get_settings

app = FastAPI()
models.Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

def raise_not_found(request):
    message = f"URL '{request.url}' doesn't exist"
    raise HTTPException(status_code=404, detail=message)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_admin_info(db_url: models.URL) -> schemas.URLInfo:
    base_url = URL(get_settings().base_url)
    admin_endpoint = app.url_path_for(
        "admin_info", secret_key=db_url.secret_key
    )
    db_url.url = str(base_url.replace(path=db_url.key))
    db_url.admin_url = str(base_url.replace(path=admin_endpoint))
    return db_url

DBSession = Annotated[Session, Depends(get_db)]

@app.get("/", response_class=HTMLResponse, name="home")
def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/create_url", response_class=HTMLResponse, name="create_url_page")
def create_url_page(request: Request):
    return templates.TemplateResponse(request, "create-key.html")

@app.get("/go", response_class=HTMLResponse, name="redirect_page")
def redirect_page(request: Request):
    return templates.TemplateResponse(request, "redirect.html")

@app.get("/manage", response_class=HTMLResponse, name="manage_page")
def manage_page(request: Request):
    return templates.TemplateResponse(request, "manage-key.html")

@app.get("/login", response_class=HTMLResponse, name="login_page")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

# for API, Swagger etc
@app.post("/create_url", response_model=schemas.URLInfo)
def create_url(url: schemas.URLBase, db: DBSession):
    db_url = crud.create_db_url(db=db, url=url)
    return get_admin_info(db_url)

@app.post("/create_url/form", response_class=HTMLResponse, name="create_url_form")
def create_url_form(request: Request, target_url: Annotated[str, Form()], db: DBSession):
    try:
        url = schemas.URLBase(target_url=target_url)
    except ValidationError as e:
        return templates.TemplateResponse(
            request, "partials/create-key-result.html",
            {"error": e.errors()[0]["msg"]},
        )

    db_url = crud.create_db_url(db=db, url=url)
    return templates.TemplateResponse(
        request, "partials/create-key-result.html",
        {"link": get_admin_info(db_url)},
    )

@app.get("/go/lookup", response_class=HTMLResponse, name="lookup_key")
def lookup_key(request: Request, db: DBSession, key: str = ""):
    # Read-only lookup for the redirect page: doesn't count as a click.
    # Keys are uppercase; the input only *displays* uppercase (CSS), so normalize here.
    key = key.strip().upper()
    db_url = None
    error = None
    if not key:
        pass  # empty field: show nothing
    elif len(key) != keygen.KEY_LENGTH:
        error = f"A key is exactly {keygen.KEY_LENGTH} characters long."
    else:
        db_url = crud.get_db_url_by_key(db=db, url_key=key)
        if not db_url:
            error = "No link with this key."
    return templates.TemplateResponse(
        request, "partials/redirect-lookup.html",
        {"link": db_url, "error": error},
    )

@app.get("/{url_key}")
def forward_to_target_url(
        url_key: str,
        request: Request,
        db: DBSession
    ):
    if db_url := crud.get_db_url_by_key(db=db, url_key=url_key):
        crud.update_db_clicks(db=db, db_url=db_url)
        return RedirectResponse(db_url.target_url)
    else:
       raise_not_found(request)

@app.get(
        "/admin/{secret_key}", 
        name="admin_info", 
        response_model=schemas.URLInfo,
)
def get_url_info(secret_key: str, request: Request, db: DBSession):
    if db_url := crud.get_db_url_by_secret_key(db, secret_key=secret_key):
        return get_admin_info(db_url)
    else:
        raise_not_found(request)

@app.delete("/admin/{secret_key}")
def delete_url(secret_key: str, request: Request, db: DBSession):
    if db_url := crud.deactivate_db_url(db, secret_key=secret_key):
        message = f"Successfully deleted shortened URL for '{db_url.target_url}'"
        return {"detail": message}
    else:
        raise_not_found(request)
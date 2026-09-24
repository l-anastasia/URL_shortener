from typing import Annotated
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import validators
from starlette.datastructures import URL



from sqlalchemy.orm import Session

from . import models, schemas, crud
from .database import SessionLocal, engine
from .config import get_settings

app = FastAPI()
models.Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

def raise_bad_request(message):
    raise HTTPException(status_code=400,
                        detail=message)

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

@app.post("/create_url", response_model=schemas.URLInfo)
def create_url(url: schemas.URLBase, db: DBSession):
    if not validators.url(url.target_url):
        raise_bad_request(message="Your provided URL is not valid")

    db_url = crud.create_db_url(db=db, url=url)
    return get_admin_info(db_url)

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
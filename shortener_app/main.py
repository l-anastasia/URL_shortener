from typing import Annotated
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from starlette.middleware.sessions import SessionMiddleware
from pydantic import ValidationError

from . import models, schemas, crud, keygen, security
from .database import engine
from .config import get_settings

from .helpers import (
    DBSession, CurrentUser,
    raise_not_found, get_admin_info, log_in, validation_error,
)

app = FastAPI()
models.Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

app.add_middleware(
    SessionMiddleware,
    secret_key=get_settings().secret_key,
    same_site="lax",
    https_only=False,
    max_age=7 * 24 * 3600
)


@app.get("/", response_class=HTMLResponse, name="home")
def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/create_url", response_class=HTMLResponse, name="create_url_page")
def create_url_page(request: Request, user: CurrentUser):
    return templates.TemplateResponse(request, "create-key.html", {"user": user})

@app.get("/go", response_class=HTMLResponse, name="redirect_page")
def redirect_page(request: Request):
    return templates.TemplateResponse(request, "redirect.html")

@app.get("/manage", response_class=HTMLResponse, name="manage_page")
def manage_page(request: Request):
    return templates.TemplateResponse(request, "manage-key.html")

@app.get("/account", response_class=HTMLResponse, name="account_page")
def account_page(request: Request, user: CurrentUser, db: DBSession):
    if user is None:
        return templates.TemplateResponse(request, "login.html")
    links = [get_admin_info(request, u) for u in crud.get_urls_by_owner(db, user.id)]
    return templates.TemplateResponse(request, "account.html", {"user": user, "links": links})

# for API, Swagger etc
@app.post("/create_url", response_model=schemas.URLInfo)
def create_url(request: Request, url: schemas.URLBase, db: DBSession):
    db_url = crud.create_db_url(db=db, url=url)
    return get_admin_info(request, db_url)

@app.post("/create_url/form", response_class=HTMLResponse, name="create_url_form")
def create_url_form(
    request: Request,
    target_url: Annotated[str, Form()],
    db: DBSession,
    user: CurrentUser,
    link_to_account: Annotated[bool, Form()] = False):
    try:
        url = schemas.URLBase(target_url=target_url)
    except ValidationError as e:
        return templates.TemplateResponse(
            request, "partials/create-key-result.html",
            {"error": validation_error(e)},
        )

    owner_id = user.id if user and link_to_account else None

    db_url = crud.create_db_url(db=db, url=url, owner_id=owner_id)
    return templates.TemplateResponse(
        request, "partials/create-key-result.html",
        {"link": get_admin_info(request, db_url)},
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

# for API, Swagger etc
@app.get(
        "/manage_key/{secret_key}", 
        name="admin_info", 
        response_model=schemas.URLInfo,
)
def manage_key(secret_key: str, request: Request, db: DBSession):
    if db_url := crud.get_db_url_by_secret_key(db, secret_key=secret_key):
        return get_admin_info(request, db_url)
    else:
        raise_not_found(request)

@app.post("/manage_key/form",
         response_class=HTMLResponse,
         name="manage_key_form")
def manage_key_form(secret_key: Annotated[str, Form()],
                    request: Request,
                    db: DBSession):
    secret_key = secret_key.strip().upper()
    db_url_info = None
    error = None
    if db_url := crud.get_db_url_by_secret_key(db, secret_key=secret_key):
        db_url_info = get_admin_info(request, db_url)
    else:
        error = "There is no link with this admin key"
    return templates.TemplateResponse(
        request, "partials/manage-key-result.html",
        {"link": db_url_info, "error": error},
    )

# for API, Swagger etc
@app.delete("/manage_key_delete/{secret_key}")
def delete_url(secret_key: str, request: Request, db: DBSession):
    if db_url := crud.deactivate_db_url_by_secret(db, secret_key=secret_key):
        message = f"Successfully deleted shortened URL for '{db_url.target_url}'"
        return {"detail": message}
    else:
        raise_not_found(request)

@app.delete("/manage_key/form",
            response_class=HTMLResponse,
            name="manage_key_delete")
def manage_key_delete(secret_key: Annotated[str, Form()],
                      request: Request,
                      db: DBSession):
    error = None
    secret_key = secret_key.strip().upper()
    db_url = crud.deactivate_db_url_by_secret(db, secret_key=secret_key)
    if not db_url:
        error = "There is no link with this admin key"
    return templates.TemplateResponse(
        request, "partials/manage-key-result.html",
        # The form was hidden when the details were shown, so an error here
        # needs a link back to it.
        {"deleted": db_url, "error": error, "back_link": True},
    )

@app.delete("/account/links/{url_key}",
            response_class=HTMLResponse,
            name="account_delete_url")
def account_delete_url(url_key: str,
                       request: Request,
                       user: CurrentUser,
                       db: DBSession):
    if user is None or not crud.deactivate_db_url_by_owner(db, url_key=url_key, owner_id=user.id):
        raise_not_found(request)
    return HTMLResponse("")

@app.post("/sign_up", response_class=HTMLResponse, name="sign_up")
def sign_up(
    request: Request,
    db: DBSession,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    email: Annotated[str, Form()] = ""
):
    try:
        user = schemas.UserCreate(
            username=username.strip().lower(),
            email=email,
            password=password,
            confirm_password=confirm_password,
        )
    except ValidationError as e:
        return templates.TemplateResponse(
            request, "partials/form-error.html", {"error": validation_error(e)}
        )
    if crud.get_user_by_username(db, user.username):
        return templates.TemplateResponse(
            request, "partials/form-error.html", {"error": "That username is taken."}
        )
    if user.email and crud.get_user_by_email(db, user.email):
        return templates.TemplateResponse(
            request, "partials/form-error.html",
            {"error": "An account with this email already exists."},
        )
    user = crud.create_user(db, user)
    log_in(request, user)
    return HTMLResponse("", headers={"HX-Redirect": str(request.url_for("account_page"))})

@app.post("/login", response_class=HTMLResponse, name="login")
def login(
    request: Request,
    db: DBSession,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    user = crud.get_user_by_username(db, username.strip().lower())
    if not user or not security.verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "partials/form-error.html",
            {"error": "Invalid username or password."},
        )
    log_in(request, user)
    return HTMLResponse("", headers={"HX-Redirect": str(request.url_for("account_page"))})

@app.post("/logout", name="logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(request.url_for("account_page"), status_code=303)
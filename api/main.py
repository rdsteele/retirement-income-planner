"""FastAPI application — mounts all routers."""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.routers.accounts import router as accounts_router
from api.routers.emr import router as emr_router

app = FastAPI(title="Retirement Income Planner")

app.include_router(emr_router, prefix="/api")
app.include_router(accounts_router, prefix="/api")
app.mount("/static", StaticFiles(directory="api/static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

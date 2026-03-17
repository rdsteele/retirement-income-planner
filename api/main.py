"""FastAPI application — mounts all routers."""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.routers.accounts import router as accounts_router
from api.routers.config import router as config_router
from api.routers.emr import router as emr_router
from api.routers.scenarios import router as scenarios_router
from api.routers.tax import router as tax_router
from api.routers.tax_years import router as tax_years_router
from api.routers.total_cost import router as total_cost_router

app = FastAPI(title="Retirement Income Planner")

app.include_router(emr_router, prefix="/api")
app.include_router(total_cost_router, prefix="/api")
app.include_router(tax_router, prefix="/api")
app.include_router(accounts_router, prefix="/api")
app.include_router(tax_years_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(scenarios_router, prefix="/api")
app.mount("/static", StaticFiles(directory="api/static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

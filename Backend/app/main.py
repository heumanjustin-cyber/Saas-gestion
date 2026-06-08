from fastapi import FastAPI

from app.db.database import engine

from app.api.company import router as company_router
from app.api.location import router as location_router
from app.api.employee import router as employee_router
from app.api.service import router as service_router
from app.api.client import router as client_router
from app.api.appointment import router as appointment_router

app = FastAPI()


@app.get("/")
def root():
    return {
        "mensaje": "Backend SaaS funcionando"
    }


@app.get("/db-test")
def db_test():
    try:
        connection = engine.connect()
        connection.close()

        return {
            "database": "conectada correctamente"
        }

    except Exception as e:
        return {
            "error": str(e)
        }


app.include_router(company_router)
app.include_router(location_router)
app.include_router(employee_router)
app.include_router(service_router)
app.include_router(client_router)
app.include_router(appointment_router)
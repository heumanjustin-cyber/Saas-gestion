from fastapi import FastAPI

from app.db.database import engine
from app.api.company import router as company_router

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
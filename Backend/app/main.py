from fastapi import FastAPI

from app.db.database import engine

from app.api.company import router as company_router
from app.api.location import router as location_router
from app.api.employee import router as employee_router
from app.api.service import router as service_router
from app.api.client import router as client_router
from app.api.appointment import router as appointment_router

from app.api.get_clients import router as get_clients_router
from app.api.get_employees import router as get_employees_router
from app.api.get_services import router as get_services_router
from app.api.get_appointments import router as get_appointments_router
from app.api.get_companies import router as get_companies_router
from app.api.get_locations import router as get_locations_router

from app.api.delete_client import router as delete_client_router
from app.api.delete_employee import router as delete_employee_router
from app.api.delete_service import router as delete_service_router
from app.api.delete_appointment import router as delete_appointment_router

from app.api.dashboard import router as dashboard_router
from app.api.get_dashboard_details import router as dashboard_details_router
from app.api.get_today_appointments import router as today_appointments_router

from app.api.auth import router as auth_router
from app.api.me import router as me_router
from app.api.register import router as register_router

from app.api.my_companies import router as my_companies_router
from app.api.my_clients import router as my_clients_router
from app.api.my_employees import router as my_employees_router
from app.api.my_services import router as my_services_router
from app.api.my_appointments import router as my_appointments_router
from app.api.my_dashboard import router as my_dashboard_router
from app.api.my_revenue import router as my_revenue_router
from app.api.my_top_services import router as my_top_services_router
from app.api.my_top_employees import router as my_top_employees_router
from app.api.my_recent_appointments import router as my_recent_appointments_router
from app.api.my_kpis import router as my_kpis_router
from app.api.my_employee_performance import router as my_employee_performance_router
from app.api.my_service_revenue import router as my_service_revenue_router
from app.api.my_business_health import router as my_business_health_router
from app.api.my_recommendations import router as my_recommendations_router
from app.api.my_growth_opportunities import router as my_growth_opportunities_router
from app.api.my_plan_recommendation import router as my_plan_recommendation_router
from app.api.company_settings import router as company_settings_router
from app.api.my_company_settings import router as my_company_settings_router
from app.api.my_setup_status import router as my_setup_status_router
from app.api.onboarding import router as onboarding_router
from app.api.access import router as access_router
from app.api.resource import router as resource_router
from app.api.employee_schedule import router as employee_schedule_router
from app.api.blocked_time import router as blocked_time_router
from app.api.resource_booking import router as resource_booking_router
from app.api.availability import router as availability_router


app = FastAPI()


@app.get("/")
def root():
    return {"mensaje": "Backend SaaS funcionando"}


@app.get("/db-test")
def db_test():
    try:
        connection = engine.connect()
        connection.close()
        return {"database": "conectada correctamente"}
    except Exception as e:
        return {"error": str(e)}


app.include_router(company_router)
app.include_router(location_router)
app.include_router(employee_router)
app.include_router(service_router)
app.include_router(client_router)
app.include_router(appointment_router)

app.include_router(get_clients_router)
app.include_router(get_employees_router)
app.include_router(get_services_router)
app.include_router(get_appointments_router)
app.include_router(get_companies_router)
app.include_router(get_locations_router)

app.include_router(delete_client_router)
app.include_router(delete_employee_router)
app.include_router(delete_service_router)
app.include_router(delete_appointment_router)

app.include_router(dashboard_router)
app.include_router(dashboard_details_router)
app.include_router(today_appointments_router)

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(register_router)

app.include_router(my_companies_router)
app.include_router(my_clients_router)
app.include_router(my_employees_router)
app.include_router(my_services_router)
app.include_router(my_appointments_router)
app.include_router(my_dashboard_router)
app.include_router(my_revenue_router)
app.include_router(my_top_services_router)
app.include_router(my_top_employees_router)
app.include_router(my_recent_appointments_router)
app.include_router(my_kpis_router)
app.include_router(my_employee_performance_router)
app.include_router(my_service_revenue_router)
app.include_router(my_business_health_router)
app.include_router(my_recommendations_router)
app.include_router(my_growth_opportunities_router)
app.include_router(my_plan_recommendation_router)
app.include_router(company_settings_router)
app.include_router(my_company_settings_router)
app.include_router(my_setup_status_router)
app.include_router(onboarding_router)
app.include_router(access_router)
app.include_router(resource_router)
app.include_router(employee_schedule_router)
app.include_router(blocked_time_router)
app.include_router(resource_booking_router)
app.include_router(availability_router)

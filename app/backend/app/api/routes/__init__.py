from fastapi import APIRouter

from app.api.routes import (
    barista_auth,
    barista_menu,
    barista_orders,
    cart,
    health,
    me,
    menu,
    orders,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(menu.router)
api_router.include_router(me.router)
api_router.include_router(cart.router)
api_router.include_router(orders.router)
api_router.include_router(barista_auth.router)
api_router.include_router(barista_orders.router)
api_router.include_router(barista_menu.router)

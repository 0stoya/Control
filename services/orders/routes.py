"""Protected read-only Order sample endpoints."""
from uuid import UUID
import psycopg
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from services.auth.gateway import AuthDenied, AuthUnavailable, session_token
from services.auth.routes import WEB, PRIVATE, error
from services.orders.access import require_order_access

def mount_order_routes(app,gateway,repository):
    def authorize(request):
        user=gateway.identity(session_token(request.headers.get('cookie','')))
        require_order_access(user)

    @app.get('/orders')
    def workspace(request:Request):
        try:
            authorize(request)
            return FileResponse(WEB/'orders.html',media_type='text/html',headers=PRIVATE)
        except AuthDenied as denied:
            if denied.status==401: return RedirectResponse('/login',status_code=303,headers=PRIVATE)
            return error(403,'Order access requires an accepted profile and account scope')
        except AuthUnavailable: return error(503,'Sign-in service is temporarily unavailable')

    def read(request,order_id=None):
        try:
            authorize(request)
            if request.url.query: return error(400,'Query parameters are not supported')
            value=repository.listing() if order_id is None else repository.detail(order_id)
            if value is None: return error(404,'Order is outside this sample')
            return JSONResponse(jsonable_encoder(value),headers=PRIVATE)
        except AuthDenied as denied: return error(denied.status,'Authentication required' if denied.status==401 else 'Order scope unavailable')
        except AuthUnavailable: return error(503,'Sign-in service is temporarily unavailable')
        except (psycopg.Error,OSError,ValueError): return error(503,'Order evidence is temporarily unavailable')

    @app.get('/api/orders')
    def listing(request:Request): return read(request)

    @app.get('/api/orders/{order_id}')
    def detail(order_id:UUID,request:Request): return read(request,order_id)

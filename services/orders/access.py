"""Shared-authority Order scope; no inferred account ownership."""
from services.auth.gateway import AuthDenied

def require_order_access(user):
    profile=user.get('operational_profile')
    if not isinstance(profile,str): raise AuthDenied(403)
    if profile in {'purchasing','planning','operations'}: return
    scope=user.get('sales_scope')
    if profile=='sales' and isinstance(scope,dict) and scope.get('mode')=='ALL': return
    raise AuthDenied(403)

def order_access_allowed(user):
    try: require_order_access(user); return True
    except AuthDenied: return False

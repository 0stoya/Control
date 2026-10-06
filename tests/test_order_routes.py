import asyncio
import json
import unittest
from uuid import UUID
from services.api.app import create_app
from services.auth.gateway import AuthGateway,AuthUnavailable
from tests.test_staff_auth import request,upstream,identity,COOKIE,TOKEN,ORIGIN

class Repository:
    def __init__(self): self.calls=[]
    def healthy(self): return True
    def listing(self): self.calls.append('list'); return {'orders':[],'coverage_state':'PARTIAL'}
    def detail(self,oid): self.calls.append(oid); return None

class OrderRouteTests(unittest.TestCase):
    def ask(self,app,path,**kwargs): return asyncio.run(request(app,path,**kwargs))
    def make(self,overrides=None,unavailable=False,enabled=True):
        repo=Repository()
        def send(*args):
            if unavailable: raise AuthUnavailable('private source details')
            return upstream(identity(**(overrides or {})))
        return create_app(lambda:True,AuthGateway(ORIGIN,send),repo if enabled else None),repo
    def headers(self): return [(b'cookie',(COOKIE+'='+TOKEN).encode())]
    def test_anonymous_outage_and_unaccepted_scope_never_read_database(self):
        for options,headers,status in (({},[],401),({'unavailable':True},self.headers(),503),
            ({'overrides':{'operational_profile':'sales','sales_scope':{'mode':'ASSIGNED'}}},self.headers(),403)):
            app,repo=self.make(**options)
            self.assertEqual(self.ask(app,'/api/orders',headers=headers)[0],status)
            self.assertEqual(repo.calls,[])
        app,repo=self.make(); self.assertEqual(self.ask(app,'/orders')[0],303)
    def test_authenticated_reads_revalidate_scope_and_do_not_accept_queries(self):
        app,repo=self.make()
        status,headers,body=self.ask(app,'/api/orders',headers=self.headers())
        self.assertEqual(status,200); self.assertEqual(headers[b'cache-control'],b'no-store')
        self.assertEqual(json.loads(body)['coverage_state'],'PARTIAL')
        self.assertEqual(self.ask(app,'/api/orders',headers=self.headers(),query=b'actor=admin')[0],400)
        self.assertEqual(repo.calls,['list'])
        oid=UUID('00000000-0000-0000-0000-000000000001')
        self.assertEqual(self.ask(app,'/api/orders/'+str(oid),headers=self.headers())[0],404)
    def test_feature_rollback_retains_sign_in_and_removes_order_routes(self):
        app,repo=self.make(enabled=False)
        self.assertEqual(self.ask(app,'/api/orders',headers=self.headers())[0],404)
        self.assertEqual(self.ask(app,'/orders',headers=self.headers())[0],404)
        result=json.loads(self.ask(app,'/api/session',headers=self.headers())[2])
        self.assertFalse(result['capabilities']['orders']); self.assertEqual(result['state'],'AUTHENTICATED')
    def test_asset_allowlist_and_text_only_ui(self):
        app,_=self.make()
        self.assertEqual(self.ask(app,'/assets/orders.js')[0],200)
        self.assertEqual(self.ask(app,'/assets/orders.css')[0],200)
        self.assertEqual(self.ask(app,'/assets/orders.html')[0],404)
        from services.auth.routes import WEB
        self.assertNotIn('innerHTML',(WEB/'orders.js').read_text())

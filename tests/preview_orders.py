"""Synthetic loopback-only visual review; never a deployment entry point."""
from datetime import datetime,timezone
from uuid import UUID
from packages.sales_sample import translate,timestamp
from services.api.app import create_app
from services.auth.gateway import AuthGateway,UpstreamResponse
from services.orders.repository import age,changes
from tests.sales_sample_fixture import sample

class PreviewAuth(AuthGateway):
    def identity(self,token): return {'user_id':1,'display_name':'Synthetic preview','operational_profile':'purchasing','permissions':['control.access']}
    def healthy(self): return True

class PreviewOrders:
    def __init__(self):
        bundle=translate(sample()); self.order_id=UUID(bundle['pointers'][0][0]); now=datetime.now(timezone.utc)
        self.history=[]; previous=None
        for row in bundle['revisions']:
            r={**row,'source_observed_at':timestamp(row['source_observed_at']),'oldest_input_at':timestamp(row['oldest_input_at']),
                'selected':row['source_snapshot_id']==3,'captured_changes':changes(previous,row['lines'])}
            self.history.append(age(r,now)); previous=row['lines']
        last=self.history[-1]
        self.order={**last,'account_reference':'SYNTHETIC_ACCOUNT','freshness_state':'UNKNOWN'}
    def listing(self): return {'orders':[self.order],'population_count':1}
    def detail(self,oid): return {'order':self.order,'history':list(reversed(self.history))} if oid==self.order_id else None
    def healthy(self): return True

if __name__=='__main__':
    import uvicorn
    auth=PreviewAuth('https://control.csscdn.co.uk',send=lambda *a:UpstreamResponse(200,b'{}'))
    uvicorn.run(create_app(lambda:True,auth,PreviewOrders()),host='127.0.0.1',port=8109,access_log=False)

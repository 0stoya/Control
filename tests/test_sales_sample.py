from copy import deepcopy
from datetime import datetime, timezone
import unittest
from packages.sales_sample import translate
from services.orders.access import require_order_access
from services.orders.repository import age,changes
from services.auth.gateway import AuthDenied
from tests.sales_sample_fixture import sample,rehash

class SalesSampleTests(unittest.TestCase):
    def test_identity_survives_renumbering_and_native_slot_reuse(self):
        b=translate(sample()); revisions=b['revisions']
        self.assertEqual(b['counts'],{'orders':1,'revisions':3,'line_inputs':5,'observations':11})
        self.assertEqual(revisions[0]['lines'][0]['line_id'],revisions[1]['lines'][1]['line_id'])
        reused=[l for r in revisions[:2] for l in r['lines'] if l['item_number']==2]
        self.assertNotEqual(reused[0]['line_id'],reused[1]['line_id'])
        self.assertEqual(revisions[2]['revision_id'],translate(sample())['revisions'][2]['revision_id'])
        self.assertEqual(changes(revisions[0]['lines'],revisions[1]['lines']),
                         {'basis':'PREVIOUS_RETAINED_CAPTURE','added':1,'removed':1,'moved':1,'values_changed':1})

    def test_null_zero_precision_and_capture_window(self):
        b=translate(sample()); lines=b['revisions'][0]['lines']
        self.assertIsNone(lines[0]['captured_quantity']); self.assertEqual(lines[1]['captured_quantity'],'0')
        self.assertEqual(lines[0]['captured_price'],'12.345678901')
        r=b['revisions'][0]; self.assertGreater(r['source_observed_at'],r['oldest_input_at'])
        self.assertTrue(all(e.occurred_at is None and e.freshness_state=='UNKNOWN' and e.coverage_state=='PARTIAL' for e in b['envelopes'].values()))
        row={'oldest_input_at':datetime(2026,10,6,10,tzinfo=timezone.utc)}
        self.assertEqual(age(row,datetime(2026,10,6,12,tzinfo=timezone.utc))['source_age_seconds'],7200)

    def test_missing_duplicate_mixed_owner_schema_epoch_and_hash_fail_closed(self):
        def duplicate(b): b['members'].append(deepcopy(b['members'][0]))
        def missing(b): b['members'].pop()
        def mixed(b): b['observations'][1]['payload']['cref']='OTHER'
        def ambiguous(b): b['observations'][2]['payload']['uniqueno']=5
        def schema(b): b['observations'][0]['schema_sha256']='d'*64
        def epoch(b): b['registry']['epoch']='restored-fork'
        def float_key(b): b['observations'][1]['payload']['uniqueno']=5.0
        def future(b): b['observations'][1]['observed_at']='2026-10-07T12:00:00+00:00'
        for mutate in (duplicate,missing,mixed,ambiguous,schema,epoch,float_key,future):
            with self.subTest(mutation=mutate.__name__):
                body=sample(); mutate(body); rehash(body)
                with self.assertRaises((ValueError,KeyError)): translate(body)
        body=sample(); body['observations'][1]['payload']['quan']=999
        with self.assertRaises(ValueError): translate(body)

    def test_auth_scope_is_explicit_and_does_not_infer_ownership_from_roles(self):
        for profile in ('purchasing','planning','operations'):
            require_order_access({'operational_profile':profile,'sales_scope':{'mode':'ASSIGNED'}})
        require_order_access({'operational_profile':'sales','sales_scope':{'mode':'ALL'}})
        for user in ({'operational_profile':'sales','sales_scope':{'mode':'ASSIGNED','rep_codes':['SYNTHETIC']}},
                     {'operational_profile':'sales'},{'roles':['administrator']},{'operational_profile':'unknown'}):
            with self.assertRaises(AuthDenied): require_order_access(user)

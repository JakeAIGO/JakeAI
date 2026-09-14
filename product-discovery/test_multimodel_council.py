import json
import os
import tempfile
import unittest
from unittest.mock import patch

import multimodel_council as council

GOOD = json.dumps({"verdict":"PASS_WITH_GATES","risks":["r"],"mitigations":["m"],"counsel_questions":[],"confidence":0.8,"rationale":"ok"})

class CouncilTests(unittest.TestCase):
    def clean_env(self): return patch.dict(os.environ, {}, clear=True)

    def test_no_keys_means_no_verified_participants(self):
        with self.clean_env(), tempfile.TemporaryDirectory() as d:
            report=council.run("packet",out_path=f"{d}/r.json",live=True)
        self.assertEqual(report["status"],"HOLD_NO_VERIFIED_RESPONSES")
        self.assertEqual(report["participating_count"],0)

    def test_keys_without_live_authorization_do_not_call_providers(self):
        env={cfg["key"]:"secret" for cfg in council.PROVIDERS.values()}
        with patch.dict(os.environ,env,clear=True),patch.object(council,"ADAPTERS",{}),tempfile.TemporaryDirectory() as d:
            report=council.run("packet",out_path=f"{d}/r.json",live=False)
        self.assertTrue(all(m["status"]=="LIVE_CALL_NOT_AUTHORIZED" for m in report["members"].values()))

    def test_all_five_success_yields_complete_pass_with_gates(self):
        env={cfg["key"]:"secret" for cfg in council.PROVIDERS.values()}
        adapters={name:(lambda n,p,k,m,name=name:(GOOD,f"req-{name}")) for name in council.PROVIDERS}
        with patch.dict(os.environ,env,clear=True),patch.object(council,"ADAPTERS",adapters),tempfile.TemporaryDirectory() as d:
            report=council.run("same frozen packet",out_path=f"{d}/r.json",live=True)
        self.assertEqual(report["status"],"COUNCIL_COMPLETE")
        self.assertEqual(report["participating_count"],5)
        self.assertEqual(report["synthesis"]["decision"],"PASS_WITH_GATES_ALL_SEATS")

    def test_any_reject_blocks(self):
        env={cfg["key"]:"secret" for cfg in council.PROVIDERS.values()}
        def adapter(name,package,key,model):
            payload=json.loads(GOOD)
            if name=="grok": payload["verdict"]="REJECT"
            return json.dumps(payload),f"req-{name}"
        with patch.dict(os.environ,env,clear=True),patch.object(council,"ADAPTERS",{n:adapter for n in council.PROVIDERS}),tempfile.TemporaryDirectory() as d:
            report=council.run("packet",out_path=f"{d}/r.json",live=True)
        self.assertEqual(report["synthesis"]["decision"],"REJECT_PRESENT")

    def test_partial_success_cannot_pass(self):
        env={council.PROVIDERS["openai"]["key"]:"secret"}
        adapters={"openai":lambda n,p,k,m:(GOOD,"req-openai"),**{k:v for k,v in council.ADAPTERS.items() if k!="openai"}}
        with patch.dict(os.environ,env,clear=True),patch.object(council,"ADAPTERS",adapters),tempfile.TemporaryDirectory() as d:
            report=council.run("packet",out_path=f"{d}/r.json",live=True)
        self.assertEqual(report["synthesis"]["decision"],"HOLD_INCOMPLETE_COUNCIL")

    def test_invalid_provider_json_is_not_participation(self):
        env={council.PROVIDERS["openai"]["key"]:"secret"}
        adapters={"openai":lambda n,p,k,m:("not-json","req-openai"),**{k:v for k,v in council.ADAPTERS.items() if k!="openai"}}
        with patch.dict(os.environ,env,clear=True),patch.object(council,"ADAPTERS",adapters),tempfile.TemporaryDirectory() as d:
            report=council.run("packet",out_path=f"{d}/r.json",live=True)
        self.assertFalse(report["members"]["openai"]["participated"])

    def test_json_extraction_accepts_fenced_response(self): self.assertEqual(council._parse("```json\n"+GOOD+"\n```")["verdict"],"PASS_WITH_GATES")
    def test_json_extraction_accepts_surrounding_commentary(self): self.assertEqual(council._parse("Here:\n"+GOOD+"\nEnd.")["verdict"],"PASS_WITH_GATES")

    def test_empty_model_environment_falls_back_to_provider_default(self):
        env={council.PROVIDERS["openai"]["key"]:"secret",council.PROVIDERS["openai"]["model_env"]:""}; seen={}
        def adapter(name,package,key,model): seen["model"]=model; return GOOD,"req-openai"
        adapters={"openai":adapter,**{k:v for k,v in council.ADAPTERS.items() if k!="openai"}}
        with patch.dict(os.environ,env,clear=True),patch.object(council,"ADAPTERS",adapters),tempfile.TemporaryDirectory() as d: council.run("packet",out_path=f"{d}/r.json",live=True)
        self.assertEqual(seen["model"],council.PROVIDERS["openai"]["model"])

    def test_safe_error_detail_keeps_metadata_and_redacts_credentials(self):
        raw=json.dumps({"error":{"type":"invalid_request_error","code":"bad","message":"API key: supersecret was rejected"}}).encode()
        detail=council._safe_error_detail(raw)
        self.assertIn("type=invalid_request_error",detail)
        self.assertIn("code=bad",detail)
        self.assertNotIn("supersecret",detail)
        self.assertIn("[REDACTED]",detail)

    def test_safe_error_detail_discards_non_json_body(self):
        self.assertEqual(council._safe_error_detail(b"secret arbitrary html"),"provider_error")

    def test_provider_http_error_contains_no_headers_or_key(self):
        err=council.ProviderHTTPError(400,"type=invalid_request; message=bad parameter")
        self.assertEqual(err.status,400)
        self.assertNotIn("Authorization",str(err))
        self.assertNotIn("secret",str(err))

if __name__=="__main__": unittest.main()

import io
import json
import os
import unittest
from unittest import mock

import model_router


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ModelRouterTests(unittest.TestCase):
    def tearDown(self):
        for key in [
            "DIRECT_MODEL_PROVIDER",
            "DIRECT_OPENAI_MODEL",
            "DIRECT_MIMO_MODEL",
            "OPENAI_API_KEY",
            "MIMO_API_KEY",
            "MIMO_BASE_URL",
            "OPENAI_BASE_URL",
        ]:
            os.environ.pop(key, None)

    def test_default_provider_preserves_openai(self):
        self.assertEqual(model_router.selected_provider(), "openai")
        self.assertEqual(model_router.selected_model(), "gpt-5.6-luna")

    def test_mimo_requires_explicit_provider_and_key(self):
        os.environ["DIRECT_MODEL_PROVIDER"] = "mimo"
        self.assertFalse(model_router.execution_configured())
        os.environ["MIMO_API_KEY"] = "test-key"
        self.assertTrue(model_router.execution_configured())
        self.assertEqual(model_router.selected_model(), "mimo-v2.6-flash")

    def test_invalid_provider_fails_closed(self):
        os.environ["DIRECT_MODEL_PROVIDER"] = "mystery"
        with self.assertRaises(model_router.ModelRouterError):
            model_router.selected_provider()
        self.assertFalse(model_router.execution_configured())

    def test_extracts_nested_responses_text(self):
        data = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}]}
        self.assertEqual(model_router.extract_response_text(data), "hello")

    @mock.patch("urllib.request.urlopen")
    def test_mimo_uses_responses_endpoint_without_tools(self, urlopen):
        os.environ["DIRECT_MODEL_PROVIDER"] = "mimo"
        os.environ["MIMO_API_KEY"] = "test-key"
        urlopen.return_value = _FakeResponse(
            {
                "id": "resp_test",
                "model": "mimo-v2.6-flash",
                "output_text": "JAKEAI_ROUTER_OK",
                "usage": {"input_tokens": 10, "output_tokens": 4},
            }
        )
        result = model_router.run_text(
            "Reply exactly JAKEAI_ROUTER_OK",
            "Follow instructions.",
            provider="mimo",
        )
        self.assertEqual(result["text"], "JAKEAI_ROUTER_OK")
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.xiaomimimo.com/v1/responses")
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["model"], "mimo-v2.6-flash")
        self.assertNotIn("tools", body)
        self.assertFalse(body["stream"])

    @mock.patch("urllib.request.urlopen")
    def test_openai_request_keeps_existing_direct_shape(self, urlopen):
        os.environ["OPENAI_API_KEY"] = "test-key"
        urlopen.return_value = _FakeResponse(
            {
                "id": "resp_openai",
                "model": "gpt-5.6-luna",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
                "usage": {"input_tokens": 5, "output_tokens": 2},
            }
        )
        result = model_router.run_text("hi", "be useful", provider="openai")
        self.assertEqual(result["text"], "ok")
        req = urlopen.call_args.args[0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["instructions"], "be useful")
        self.assertEqual(body["reasoning"]["effort"], "low")
        self.assertFalse(body["store"])


if __name__ == "__main__":
    unittest.main()

import importlib.util
import os
import sys
import tempfile
from types import SimpleNamespace

import pytest

class FakeStripe:
    api_key = None
    class Price:
        @staticmethod
        def retrieve(price_id):
            return SimpleNamespace(id=price_id, active=True, livemode=False, unit_amount=2900, recurring=SimpleNamespace(interval="month"))

sys.modules["stripe"] = FakeStripe
spec = importlib.util.spec_from_file_location("direct_subscription", "direct_subscription.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def mk_sub(status="active", cancel=False, sub_id="sub_test", customer="cus_test"):
    return SimpleNamespace(
        id=sub_id,
        customer=customer,
        status=status,
        current_period_end=9999999999,
        cancel_at_period_end=cancel,
        items=SimpleNamespace(data=[SimpleNamespace(price=SimpleNamespace(id="price_test"))]),
    )

@pytest.fixture(autouse=True)
def env():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DIRECT_DATABASE_PATH"] = path
    os.environ["DIRECT_STRIPE_PRICE_ID"] = "price_test"
    os.environ["DIRECT_STRIPE_EXPECT_LIVEMODE"] = "false"
    os.environ["DIRECT_BILLING_ENABLED"] = "true"
    os.environ["DIRECT_STRIPE_SECRET_KEY"] = "sk_test_fake"
    os.environ["DIRECT_USAGE_ALLOWANCE_CENTS"] = "1000"
    mod.init_direct_db()
    yield
    try:
        os.remove(path)
    except OSError:
        pass

def test_price_shape_and_environment_gate():
    mod._assert_billing_config()

def test_cancel_at_period_end_preserves_usage():
    mod._upsert_entitlement(mk_sub())
    assert mod._consume_usage("sub_test", 400)["remaining_cents"] == 600
    mod._upsert_entitlement(mk_sub(cancel=True))
    conn = mod._conn()
    row = conn.execute("SELECT usage_cents,cancel_at_period_end,status FROM direct_entitlements WHERE stripe_subscription_id='sub_test'").fetchone()
    conn.close()
    assert row["usage_cents"] == 400
    assert row["cancel_at_period_end"] == 1
    assert row["status"] == "active"

def test_hard_stop_rejects_overage_without_mutating_usage():
    mod._upsert_entitlement(mk_sub())
    mod._consume_usage("sub_test", 900)
    with pytest.raises(Exception) as exc:
        mod._consume_usage("sub_test", 101)
    assert getattr(exc.value, "status_code", None) == 402
    conn = mod._conn()
    row = conn.execute("SELECT usage_cents FROM direct_entitlements WHERE stripe_subscription_id='sub_test'").fetchone()
    conn.close()
    assert row["usage_cents"] == 900

def test_inactive_subscription_cannot_consume_usage():
    mod._upsert_entitlement(mk_sub(status="past_due"))
    with pytest.raises(Exception) as exc:
        mod._consume_usage("sub_test", 1)
    assert getattr(exc.value, "status_code", None) == 402

def test_invoice_cycle_resets_allowance_usage():
    mod._upsert_entitlement(mk_sub())
    mod._consume_usage("sub_test", 777)
    mod._upsert_entitlement(mk_sub(), reset_usage=True)
    conn = mod._conn()
    row = conn.execute("SELECT usage_cents FROM direct_entitlements WHERE stripe_subscription_id='sub_test'").fetchone()
    conn.close()
    assert row["usage_cents"] == 0

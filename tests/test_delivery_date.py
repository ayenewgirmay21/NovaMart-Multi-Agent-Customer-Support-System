import importlib.util
import sys
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# Import the helper without loading real AWS configuration or clients.
fake_config = types.ModuleType("config")
fake_config.AWS_REGION = "us-east-1"
fake_config.ORDERS_TABLE = "mock-orders"
fake_config.CUSTOMERS_TABLE = "mock-customers"
fake_config.WORKFLOW_STATE_TABLE = "mock-workflow"
fake_config.ORCHESTRATOR_MODEL_ID = "mock-orchestrator-model"
fake_config.WORKER_MODEL_ID = "mock-worker-model"
fake_config.GUARDRAIL_ID = ""
fake_config.GUARDRAIL_VERSION = ""

fake_strands = types.ModuleType("strands")
fake_strands.Agent = MagicMock(name="Agent")
fake_models = types.ModuleType("strands.models")
fake_models.BedrockModel = MagicMock(name="BedrockModel")
fake_utils = types.ModuleType("src.agent_utils")
fake_utils.AgentTrace = MagicMock(name="AgentTrace")
fake_observability = types.ModuleType("src.agent_observability")
fake_observability.tool = lambda function: function
fake_kb = types.ModuleType("src.bedrock_kb_retrieval")
fake_kb.retrieve_from_knowledge_base = MagicMock()

fake_modules = {
    "config": fake_config,
    "strands": fake_strands,
    "strands.models": fake_models,
    "src.agent_utils": fake_utils,
    "src.agent_observability": fake_observability,
    "src.bedrock_kb_retrieval": fake_kb,
}

sys.modules.pop("agent_orchestrator", None)
with patch.dict(sys.modules, fake_modules), \
     patch("boto3.resource") as mock_resource, \
     patch("boto3.client"):
    mock_resource.return_value.Table.return_value = MagicMock()
    spec = importlib.util.spec_from_file_location(
        "agent_orchestrator", ROOT / "src" / "agent_orchestrator.py"
    )
    ao = importlib.util.module_from_spec(spec)
    sys.modules["agent_orchestrator"] = ao
    spec.loader.exec_module(ao)


class TestDeliveryDate(unittest.TestCase):
    TODAY = date(2026, 10, 9)

    def test_past_estimate_is_flagged_without_claiming_delivery(self):
        order = {
            "order_id": "ORD-54072",
            "status": "processing",
            "estimated_delivery": "2026-09-17",
        }
        result = ao._annotate_delivery_date(order, self.TODAY)
        self.assertEqual(result["delivery_date_check"], "PAST_DUE_UNCONFIRMED")
        self.assertIn("has passed", result["delivery_date_warning"])
        self.assertIn("does not confirm delivery", result["delivery_date_warning"])

    def test_delivered_status_is_respected(self):
        result = ao._annotate_delivery_date(
            {"status": "delivered", "estimated_delivery": "2026-09-17"},
            self.TODAY,
        )
        self.assertEqual(result["delivery_date_check"], "DELIVERY_CONFIRMED")
        self.assertNotIn("delivery_date_warning", result)

    def test_future_estimate_is_not_flagged_past_due(self):
        result = ao._annotate_delivery_date(
            {"status": "processing", "estimated_delivery": "2026-10-20"},
            self.TODAY,
        )
        self.assertEqual(result["delivery_date_check"], "NOT_PAST_DUE")
        self.assertNotIn("delivery_date_warning", result)

    def test_missing_or_invalid_date_is_not_guessed(self):
        for order in (
            {"status": "processing"},
            {"status": "processing", "estimated_delivery": "not-a-date"},
        ):
            with self.subTest(order=order):
                result = ao._annotate_delivery_date(order, self.TODAY)
                self.assertNotIn("delivery_date_check", result)
                self.assertNotIn("delivery_date_warning", result)

    def test_original_order_is_not_modified(self):
        order = {
            "status": "processing",
            "estimated_delivery": "2026-09-17",
        }
        original = dict(order)
        result = ao._annotate_delivery_date(order, self.TODAY)
        self.assertEqual(order, original)
        self.assertIsNot(result, order)


if __name__ == "__main__":
    unittest.main(verbosity=2)
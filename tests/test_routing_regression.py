import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# Supply fake configuration and dependencies before importing application code.
fake_config = types.ModuleType("config")
fake_config.AWS_REGION = "us-east-1"
fake_config.ORDERS_TABLE = "mock-orders"
fake_config.CUSTOMERS_TABLE = "mock-customers"
fake_config.WORKFLOW_STATE_TABLE = "mock-workflow"
fake_config.ORCHESTRATOR_MODEL_ID = "mock-orchestrator-model"
fake_config.WORKER_MODEL_ID = "mock-worker-model"
fake_config.GUARDRAIL_ID = ""
fake_config.GUARDRAIL_VERSION = ""
fake_config.GUARDRAIL_NAME = "mock-guardrail"

fake_strands = types.ModuleType("strands")
fake_strands.Agent = MagicMock(name="Agent")

fake_strands_models = types.ModuleType("strands.models")
fake_strands_models.BedrockModel = MagicMock(name="BedrockModel")

fake_agent_utils = types.ModuleType("src.agent_utils")
fake_agent_utils.AgentTrace = MagicMock(name="AgentTrace")

fake_observability = types.ModuleType("src.agent_observability")
fake_observability.tool = lambda function: function

fake_kb = types.ModuleType("src.bedrock_kb_retrieval")
fake_kb.retrieve_from_knowledge_base = MagicMock(
    name="retrieve_from_knowledge_base"
)

fake_modules = {
    "config": fake_config,
    "strands": fake_strands,
    "strands.models": fake_strands_models,
    "src.agent_utils": fake_agent_utils,
    "src.agent_observability": fake_observability,
    "src.bedrock_kb_retrieval": fake_kb,
}

# Clear a previously cached module if this test is run in an interactive process.
sys.modules.pop("agent_orchestrator", None)

with patch.dict(sys.modules, fake_modules), \
     patch("boto3.resource") as mock_resource, \
     patch("boto3.client") as mock_client:
    mock_resource.return_value.Table.return_value = MagicMock()
    ao = importlib.import_module("agent_orchestrator")


class TestRoutingRegression(unittest.TestCase):
    def setUp(self):
        self.session_id = "local-regression-session"
        self.state = {
            "session_id": self.session_id,
            "customer_id": "CUST-TEST",
            "version": 1,
            "status": "INITIALIZED",
            "inventory_findings": None,
            "policy_findings": None,
            "refund_decision": None,
            "final_response": None,
        }

    def test_inventory_route_updates_state_without_invoking_refund(self):
        inventory = MagicMock(return_value="Order status: processing")
        refund = MagicMock(side_effect=AssertionError(
            "Refund worker must not be invoked by the inventory route"
        ))
        workers = (inventory, MagicMock(), refund, MagicMock())

        with patch.object(ao, "_get_workers", return_value=workers), \
             patch.object(ao, "_read_workflow_state",
                          return_value=self.state), \
             patch.object(
                 ao, "_update_workflow_state",
                 return_value={**self.state, "version": 2}
             ) as update:
            result = ao.route_to_inventory_agent(
                self.session_id, "Where is my order?"
            )

        inventory.assert_called_once()
        refund.assert_not_called()
        update.assert_called_once()
        self.assertEqual(result["agent"], "InventoryAgent")
        self.assertIn("Order status: processing", result["result"])

    def test_communication_route_saves_final_response(self):
        communication = MagicMock(
            return_value="Your order is processing. Thank you."
        )
        workers = (MagicMock(), MagicMock(), MagicMock(), communication)

        with patch.object(ao, "_get_workers", return_value=workers), \
             patch.object(ao, "_read_workflow_state",
                          return_value=self.state), \
             patch.object(
                 ao, "_update_workflow_state",
                 return_value={**self.state, "version": 2}
             ) as update:
            result = ao.route_to_communication_agent(
                self.session_id, "Where is my order?"
            )

        communication.assert_called_once()
        update.assert_called_once()
        self.assertEqual(result["agent"], "CommunicationAgent")
        self.assertIn("Thank you", result["final_response"])

    def test_inventory_route_persists_overdue_delivery_warning(self):
        warning = (
            "The estimated delivery date 2026-09-17 has passed "
            "as of 2026-10-09. The recorded order status is 'processing', "
            "and the available record does not confirm delivery."
        )
        inventory = MagicMock(return_value="Order status: processing")
        workers = (inventory, MagicMock(), MagicMock(), MagicMock())
        saved = {}

        def save_state(session_id, changes, expected_version):
            saved.update(changes)
            return {**self.state, **changes, "version": 2}

        order = {
            "order_id": "ORD-54072",
            "status": "processing",
            "estimated_delivery": "2026-09-17",
            "delivery_date_warning": warning,
        }

        with (
            patch.object(ao, "_get_workers", return_value=workers),
            patch.object(ao, "_read_workflow_state", return_value=self.state),
            patch.object(ao, "check_order_status", return_value=order) as lookup,
            patch.object(ao, "_update_workflow_state", side_effect=save_state),
        ):
            result = ao.route_to_inventory_agent(
                self.session_id, "Where is order ORD-54072?"
            )

        lookup.assert_called_once_with("CUST-TEST", "ORD-54072")
        self.assertIn(warning, saved["inventory_findings"])
        self.assertEqual(result["result"], "Order status: processing")
        self.assertEqual(saved["inventory_agent"], "Order status: processing")

    def test_inventory_route_rejects_missing_state(self):
        with patch.object(
            ao, "_get_workers",
            return_value=(MagicMock(), MagicMock(),
                          MagicMock(), MagicMock())
        ), patch.object(ao, "_read_workflow_state", return_value={}):
            with self.assertRaises(KeyError):
                ao.route_to_inventory_agent(
                    self.session_id, "Where is my order?"
                )

    def test_orchestrator_prompt_contains_both_routing_rules(self):
        with patch.object(ao, "_model", return_value=MagicMock()), \
             patch.object(ao, "Agent") as agent_factory:
            ao.build_orchestrator_agent()

        prompt = agent_factory.call_args.kwargs["system_prompt"]
        self.assertIn(
            "Inventory then Communication; NEVER", prompt
        )
        self.assertIn(
            "For explicit return or refund requests: Inventory then Refund",
            prompt,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
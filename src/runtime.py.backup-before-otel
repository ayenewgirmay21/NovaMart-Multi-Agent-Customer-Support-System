import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from src.agent_orchestrator import build_orchestrator_agent

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = build_orchestrator_agent()
    return _orchestrator


@app.entrypoint
def invoke(payload):
    """AgentCore Runtime entrypoint for NovaMart customer support."""
    if isinstance(payload, dict):
        query = (
            payload.get("query")
            or payload.get("prompt")
            or payload.get("input")
            or ""
        )
        customer_id = payload.get("customer_id", "CUST-001")
        session_id = payload.get("session_id", "")
    else:
        query = str(payload)
        customer_id = "CUST-001"
        session_id = ""

    query = str(query).strip()

    if not query:
        return {
            "error": "A customer support query is required."
        }

    context = f"[Customer ID: {customer_id}]"
    if session_id:
        context += f" [Session ID: {session_id}]"

    prompt = f"{context} {query}"

    try:
        response = _get_orchestrator()(prompt)
        return {
            "response": str(response),
            "customer_id": customer_id,
            "session_id": session_id,
        }
    except Exception:
        logger.exception("NovaMart runtime invocation failed")
        raise


if __name__ == "__main__":
    app.run()

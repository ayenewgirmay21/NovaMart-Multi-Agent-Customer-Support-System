import logging

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from src.agent_orchestrator import build_orchestrator_agent

logger = logging.getLogger(__name__)
app = BedrockAgentCoreApp()
tracer = trace.get_tracer("novamart.runtime")
_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = build_orchestrator_agent()
    return _orchestrator


@app.entrypoint
def invoke(payload):
    """AgentCore Runtime entrypoint with OpenTelemetry tracing."""
    with tracer.start_as_current_span("novamart.runtime.invoke") as span:
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
        span.set_attribute("novamart.customer_id", str(customer_id))
        if session_id:
            span.set_attribute("novamart.session_id", str(session_id))

        if not query:
            span.set_status(Status(StatusCode.ERROR, "Empty customer query"))
            return {"error": "A customer support query is required."}

        context = f"[Customer ID: {customer_id}]"
        if session_id:
            context += f" [Session ID: {session_id}]"

        try:
            response = _get_orchestrator()(f"{context} {query}")
            span.set_status(Status(StatusCode.OK))
            return {
                "response": str(response),
                "customer_id": customer_id,
                "session_id": session_id,
            }
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            logger.exception("NovaMart runtime invocation failed")
            raise


if __name__ == "__main__":
    app.run()

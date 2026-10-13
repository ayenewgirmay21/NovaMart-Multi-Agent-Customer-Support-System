import json
import uuid
import boto3

REGION = "us-east-1"
RUNTIME_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:965667640672:"
    "runtime/novamart_customer_support-5VyHr473qq"
)

client = boto3.client("bedrock-agentcore", region_name=REGION)

session_id = "novamart-client-" + uuid.uuid4().hex

payload = {
    "customer_id": "CUST-001",
    "session_id": session_id,
    "query": "Please check my orders and summarize their current status."
}

print("Invoking NovaMart AgentCore Runtime...")
print("Customer ID:", payload["customer_id"])
print("Session ID:", payload["session_id"])

response = client.invoke_agent_runtime(
    agentRuntimeArn=RUNTIME_ARN,
    runtimeSessionId=session_id,
    payload=json.dumps(payload).encode("utf-8"),
    qualifier="DEFAULT",
)

print("HTTP status:", response.get("statusCode"))

body = response.get("response")
if body is not None:
    if hasattr(body, "read"):
        body = body.read()

    if isinstance(body, bytes):
        body = body.decode("utf-8")

    try:
        result = json.loads(body)
        print("\nRuntime response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("\nReturned session ID:", result.get("session_id"))
    except (json.JSONDecodeError, TypeError):
        print(body)
else:
    print(json.dumps(response, indent=2, default=str))

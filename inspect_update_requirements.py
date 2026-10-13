import boto3

c = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
op = c.meta.service_model.operation_model("UpdateAgentRuntime")
print("Required fields:", op.input_shape.required_members)

r = c.get_agent_runtime(
    agentRuntimeId="novamart_customer_support-5VyHr473qq"
)
print("\nAvailable runtime fields:")
for key in sorted(r.keys()):
    if key not in ("agentRuntimeArtifact", "responseMetadata"):
        print(f"  {key}: {r[key]}")

for key in ("networkConfiguration", "protocolConfiguration",
            "lifecycleConfiguration", "metadataConfiguration",
            "capacityProviderConfiguration"):
    if key in r:
        print(f"\n{key}: {r[key]}")

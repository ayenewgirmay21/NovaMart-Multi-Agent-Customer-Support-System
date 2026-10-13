import boto3
import json

client = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
operation = client.meta.service_model.operation_model("UpdateAgentRuntime")
shape = operation.input_shape

print("UpdateAgentRuntime input fields:")
for name, member in shape.members.items():
    print(f"  {name}: {member.type_name}")

print("\nAgentRuntimeArtifact schema:")
artifact = shape.members.get("agentRuntimeArtifact")
if artifact:
    for name, member in artifact.members.items():
        print(f"  {name}: {member.type_name}")
        if name == "codeConfiguration":
            for field, detail in member.members.items():
                print(f"    {field}: {detail.type_name}")
                if field == "entryPoint":
                    print("      item type:", detail.member.type_name)

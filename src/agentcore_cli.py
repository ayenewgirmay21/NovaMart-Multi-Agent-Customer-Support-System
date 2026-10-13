"""
Small AgentCore Runtime deployment wrapper used by the NovaMart project.

The project orchestrator calls this module instead of directly calling the
AgentCore Runtime create API. The wrapper uses the AWS CLI where possible so
the project remains easy to run from the Udacity environment.
"""

import json
import os
import subprocess
from typing import Any, Dict, Optional


_runtime_config: Dict[str, Any] = {}
_deployed_runtime_arn: Optional[str] = None


def _run_aws(args: list[str]) -> str:
    """Run an AWS CLI command and return stdout, raising on failure."""
    command = ["aws", *args]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"AWS CLI command failed ({result.returncode}): "
            f"{' '.join(command)}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def configure_runtime(
    *,
    network_mode: str = "PUBLIC",
    protocol: str = "HTTP",
    execution_role_arn: Optional[str] = None,
    environment_variables: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Store AgentCore Runtime deployment configuration.

    Parameters:
        network_mode: Runtime network mode, normally PUBLIC for this project.
        protocol: Runtime protocol, normally HTTP.
        execution_role_arn: IAM execution role ARN.
        environment_variables: Runtime environment variables.
        **kwargs: Additional project/runtime options.

    Returns:
        The stored runtime configuration.
    """
    global _runtime_config

    _runtime_config = {
        "network_mode": network_mode,
        "protocol": protocol,
        "execution_role_arn": execution_role_arn,
        "environment_variables": environment_variables or {},
        **kwargs,
    }

    return dict(_runtime_config)


def deploy() -> str:
    """
    Deploy the configured AgentCore runtime.

    Returns:
        Runtime ARN returned by the AgentCore control plane.
    """
    global _deployed_runtime_arn

    if not _runtime_config:
        raise RuntimeError(
            "AgentCore runtime is not configured. "
            "Call configure_runtime() first."
        )

    # Prefer the AgentCore CLI if it is installed in the environment.
    env = os.environ.copy()

    # The project environment may expose the AgentCore CLI as either
    # `agentcore` or `aws-agentcore`.
    candidates = [r"D:\Scripts\agentcore.exe", "agentcore.cmd", "aws-agentcore.cmd", "agentcore", "aws-agentcore"]

    last_error = None
    for executable in candidates:
        try:
            command = [executable, "deploy"]

            # Pass configuration through environment variables. This keeps
            # secrets and long values out of command-line arguments.
            env["AGENTCORE_NETWORK_MODE"] = str(
                _runtime_config.get("network_mode", "PUBLIC")
            )
            env["AGENTCORE_PROTOCOL"] = str(
                _runtime_config.get("protocol", "HTTP")
            )

            role = _runtime_config.get("execution_role_arn")
            if role:
                env["AGENTCORE_EXECUTION_ROLE_ARN"] = str(role)

            runtime_env = _runtime_config.get("environment_variables", {})
            env["AGENTCORE_RUNTIME_ENV_VARS"] = json.dumps(runtime_env)

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            if result.returncode == 0:
                # Try to extract an ARN from the CLI output.
                output = (result.stdout or "") + "\n" + (result.stderr or "")
                for token in output.split():
                    if token.startswith("arn:aws:bedrock-agentcore:"):
                        _deployed_runtime_arn = token.strip(
                            "\"',.;()[]{}"
                        )
                        break

                if _deployed_runtime_arn:
                    return _deployed_runtime_arn

                return output.strip()

            last_error = result.stderr.strip()

        except FileNotFoundError as exc:
            last_error = str(exc)

    raise RuntimeError(
        "No supported AgentCore CLI executable was found. "
        "Install/configure the AgentCore CLI in the Udacity environment. "
        f"Last error: {last_error}"
    )


def deployed_runtime_arn() -> str:
    """
    Return the ARN captured during deployment.

    Returns:
        The deployed AgentCore Runtime ARN.

    Raises:
        RuntimeError: If deploy() has not returned an ARN yet.
    """
    if _deployed_runtime_arn:
        return _deployed_runtime_arn

    value = os.getenv("AGENTCORE_RUNTIME_ARN")
    if value:
        return value

    raise RuntimeError(
        "No deployed runtime ARN is available. Run deploy() first or set "
        "AGENTCORE_RUNTIME_ARN."
    )


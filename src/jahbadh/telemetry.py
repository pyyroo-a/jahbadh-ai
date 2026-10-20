"""Tracing: Agent Framework's OpenTelemetry spans go to Application Insights, where Foundry's Tracing page reads them.

Off unless APPLICATIONINSIGHTS_CONNECTION_STRING is set, so local runs and tests send nothing anywhere.
"""

import os
from collections.abc import Mapping

from agent_framework.observability import create_resource, enable_instrumentation
from azure.monitor.opentelemetry import configure_azure_monitor

CONNECTION_STRING = "APPLICATIONINSIGHTS_CONNECTION_STRING"
_started = False


def setup_tracing(env: Mapping[str, str] = os.environ) -> bool:
    """Turn tracing on when a connection string is set. Safe to call more than once. True when tracing is on."""
    global _started
    connection = (env.get(CONNECTION_STRING) or "").strip()
    if not connection:
        return False
    if not _started:
        configure_azure_monitor(connection_string=connection, resource=create_resource(service_name="jahbadh"))
        # prompts and replies are synthetic match data with no viewer input, so they are traced in full
        enable_instrumentation(enable_sensitive_data=True)
        _started = True
    return True

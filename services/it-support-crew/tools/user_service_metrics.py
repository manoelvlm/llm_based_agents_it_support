import json
import logging
from typing import Any, Dict, Optional, Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class UserServiceMetricsToolInput(BaseModel):
    """Input schema for the UserServiceMetricsTool."""

    endpoint: str = Field(
        default="metrics",
        description="Endpoint to query: 'metrics', 'health', or 'alerts'. Defaults to metrics.",
    )


class UserServiceMetricsTool(BaseTool):
    name: str = "UserServiceMetricsTool"
    description: str = """
    Tool for collecting metrics from the user service.
    Use this tool to:
    1. Query the user API metrics
    2. Check the service health status
    3. Analyze database connections and other critical indicators
    4. Retrieve current alerts from Prometheus
    """
    args_schema: Type[BaseModel] = UserServiceMetricsToolInput

    def _run(self, endpoint: str = "metrics") -> str:
        """
        Executes the metrics collection tool for the user-service.

        Args:
            endpoint (str): The endpoint to query: 'metrics', 'health', or 'alerts'.
                         Default is 'metrics'.

        Returns:
            str: Formatted metrics collection result
        """
        try:
            # Update URL to access the service exposed on the host port
            metrics_url = "http://localhost:5001/metrics"
            health_url = "http://localhost:5001/health"
            alerts_url = "http://localhost:9090/api/v1/alerts"

            logger.info(f"Collecting metrics from user-service")

            # If alerts endpoint was requested
            if endpoint.lower() == "alerts":
                return self._get_prometheus_alerts(alerts_url)

            # Health check
            health_response = requests.get(health_url, timeout=10)

            if health_response.status_code != 200:
                health_data = (
                    f"ALERT: Service reported unhealthy status: {health_response.text}"
                )
            else:
                health_data = f"Health status: {health_response.json()}"

            # If only the health endpoint was requested
            if endpoint.lower() == "health":
                return health_data

            # Metrics query
            metrics_response = requests.get(metrics_url, timeout=10)

            if metrics_response.status_code != 200:
                return f"Error collecting metrics: {metrics_response.status_code}\n{health_data}"

            metrics_raw = metrics_response.text

            # Basic processing to make the output more readable
            processed_output = self._process_metrics(metrics_raw)

            return f"{health_data}\n\n{processed_output}"

        except requests.exceptions.RequestException as e:
            logger.error(f"Error collecting metrics: {str(e)}")
            return f"Error connecting to metrics service: {str(e)}"

    def _get_prometheus_alerts(self, alerts_url: str) -> str:
        """
        Retrieves and formats current alerts from Prometheus.

        Args:
            alerts_url (str): URL for the Prometheus alerts API endpoint

        Returns:
            str: Formatted alert information
        """
        try:
            response = requests.get(alerts_url, timeout=10)

            if response.status_code != 200:
                return f"Error retrieving alerts: HTTP {response.status_code}"

            alerts_data = response.json()

            if not alerts_data.get("data", {}).get("alerts", []):
                return "No active alerts found in Prometheus."

            active_alerts = alerts_data.get("data", {}).get("alerts", [])
            formatted_alerts = "Current Prometheus Alerts:\n\n"

            for idx, alert in enumerate(active_alerts, 1):
                alert_name = alert.get("labels", {}).get("alertname", "Unnamed Alert")
                severity = alert.get("labels", {}).get("severity", "unknown")
                status = alert.get("state", "unknown")
                summary = alert.get("annotations", {}).get(
                    "summary", "No summary available"
                )
                description = alert.get("annotations", {}).get(
                    "description", "No description available"
                )

                formatted_alerts += f"Alert #{idx}: {alert_name}\n"
                formatted_alerts += f"Status: {status}\n"
                formatted_alerts += f"Severity: {severity}\n"
                formatted_alerts += f"Summary: {summary}\n"
                formatted_alerts += f"Description: {description}\n\n"

            return formatted_alerts

        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving Prometheus alerts: {str(e)}")
            return f"Error connecting to Prometheus: {str(e)}"

    def _process_metrics(self, metrics_text: str) -> str:
        """
        Processes the raw metrics text to make it more readable.
        """
        processed_lines = []

        # Important metrics to highlight
        key_metrics = [
            "http_requests_total",
            "http_request_duration_seconds",
            "database_health",
            "redis_health",
            "http_requests_in_progress",
            "sql_alchemy_pool_connections",
            "database_error_total",
            "database_query_duration_seconds",
        ]

        lines = metrics_text.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Highlight important metrics
            for key in key_metrics:
                if key in line and not line.startswith("#"):
                    processed_lines.append(f"[IMPORTANT] {line}")
                    break
            else:
                processed_lines.append(line)

        # Analyze pool connections
        connections_used = None
        connections_total = None

        for line in lines:
            if "sql_alchemy_pool_connections_used" in line and not line.startswith("#"):
                try:
                    connections_used = float(line.split()[1])
                except (ValueError, IndexError):
                    pass

            if "sql_alchemy_pool_connections_total" in line and not line.startswith(
                "#"
            ):
                try:
                    connections_total = float(line.split()[1])
                except (ValueError, IndexError):
                    pass

        if connections_used is not None and connections_total is not None:
            usage_percent = (
                (connections_used / connections_total) * 100
                if connections_total > 0
                else 0
            )
            pool_status = f"\nConnection Pool Analysis:\n"
            pool_status += f"- Connections in use: {connections_used}\n"
            pool_status += f"- Total connections: {connections_total}\n"
            pool_status += f"- Utilization: {usage_percent:.1f}%\n"

            if usage_percent > 80:
                pool_status += "- ALERT: Connection pool close to limit!\n"

            processed_lines.append(pool_status)

        return "\n".join(processed_lines)

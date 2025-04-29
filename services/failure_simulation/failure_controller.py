import datetime
import importlib
import logging
import os
import sys
import threading
import time

import docker
from flask import Flask, jsonify, request

# Advanced logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("chaos-engineering")

app = Flask(__name__)
client = docker.from_env()

# Startup log
logger.info("Starting Failure Simulation Application")

FAILURE_TYPES = {
    "hardware": ["cpu_overload", "memory_leak"],
}

logger.info(f"Configured failure types: {FAILURE_TYPES}")

# Track active failures
active_failures = {}
# Lock to ensure thread-safe operations on active_failures
failure_lock = threading.Lock()


# Load simulation modules dynamically
def load_simulation_module(failure_type):
    """Dynamically load the appropriate simulation module for the failure type."""
    try:
        # Convert failure_type to module name format (e.g. cpu_overload -> cpu_overload_simulation)
        module_name = f"simulations.{failure_type}_simulation"
        module = importlib.import_module(module_name)
        return module
    except ImportError as e:
        logger.error(f"Failed to import simulation module for {failure_type}: {e}")
        raise Exception(f"Simulation module for {failure_type} not found")


@app.route("/failures", methods=["POST"])
def create_failure():
    logger.info("Received request to create failure")

    data = request.get_json()
    logger.debug(f"Received data: {data}")

    failure_type = data.get("type")
    service = data.get("service")
    duration = data.get("duration", 60)  # Default 60 seconds if not specified
    intensity = data.get("intensity", "low")  # Default "low" if not specified

    if not failure_type or not service:
        logger.error("Missing required parameters: type or service")
        return jsonify({"error": "Missing required parameters"}), 400

    category = None
    for cat, failures in FAILURE_TYPES.items():
        if failure_type in failures:
            category = cat
            break

    if not category:
        logger.error(f"Unknown failure type: {failure_type}")
        return jsonify({"error": f"Unknown failure type: {failure_type}"}), 400

    # Check if there's an active failure
    with failure_lock:
        if active_failures:
            logger.warning("A failure is already in progress. Cannot start a new one.")
            current_failure = list(active_failures.values())[0]

            # Fix: Calculate remaining time by converting string to timestamp
            end_time_dt = datetime.datetime.strptime(
                current_failure["end_time"], "%Y-%m-%d %H:%M:%S"
            )
            end_time_float = end_time_dt.timestamp()
            time_remaining = max(0, end_time_float - time.time())

            return (
                jsonify(
                    {
                        "error": "A failure is already in progress",
                        "active_failure": current_failure,
                        "time_remaining": round(time_remaining, 2),
                    }
                ),
                409,
            )

        failure_id = f"{service}_{failure_type}_{int(time.time())}"
        logger.info(f"Creating failure with ID: {failure_id}")

        try:
            # Check if the container exists
            try:
                container = client.containers.get(service)
                logger.info(f"Container found: {service} (ID: {container.id})")
            except docker.errors.NotFound:
                logger.error(f"Container not found: {service}")
                return jsonify({"error": f"Container '{service}' not found"}), 404
            except Exception as e:
                logger.error(f"Error accessing Docker API: {e}")
                return jsonify({"error": f"Error accessing Docker API: {str(e)}"}), 500

            # Load and run the appropriate simulation module
            try:
                simulation_module = load_simulation_module(failure_type)
                logger.info(
                    f"Implementing {category} failure: {failure_type} with intensity {intensity}"
                )
                simulation_module.implement(container, intensity)
            except Exception as e:
                logger.error(f"Error implementing failure: {str(e)}", exc_info=True)
                return jsonify({"error": f"Error implementing failure: {str(e)}"}), 500

            # Store active failure information with both string and numeric timestamp
            active_failures[failure_id] = {
                "type": failure_type,
                "service": service,
                "intensity": intensity,
                "start_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": (
                    datetime.datetime.now() + datetime.timedelta(seconds=duration)
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "end_time_numeric": time.time()
                + duration,  # Add numeric timestamp for calculations
                "duration_seconds": duration,  # Keep the original duration for calculations
            }
            logger.info(f"Active failure added: {active_failures[failure_id]}")

            # Schedule automatic recovery if duration is positive
            if duration > 0:
                logger.info(f"Scheduling automatic recovery in {duration} seconds")
                threading.Timer(duration, recover_failure, args=[failure_id]).start()

            return (
                jsonify(
                    {
                        "id": failure_id,
                        "message": f"Failure {failure_type} implemented on {service}",
                    }
                ),
                201,
            )
        except Exception as e:
            logger.error(f"Error implementing failure: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500


def recover_failure(failure_id):
    logger.info(f"Starting recovery for failure: {failure_id}")

    with failure_lock:
        if failure_id not in active_failures:
            logger.warning(f"Failure {failure_id} not found for recovery")
            return

        failure = active_failures[failure_id]
        service = failure["service"]
        failure_type = failure["type"]
        logger.info(f"Recovering from {failure_type} failure on service {service}")

        try:
            container = client.containers.get(service)
            # Load and run recovery from the appropriate simulation module
            simulation_module = load_simulation_module(failure_type)
            simulation_module.recover(container)
            del active_failures[failure_id]
            logger.info(f"Failure {failure_id} successfully recovered")
        except docker.errors.NotFound:
            logger.error(f"Container {service} not found during recovery")
            # Remove the failure from active_failures even if container not found
            del active_failures[failure_id]
        except Exception as e:
            logger.error(
                f"Error recovering from failure {failure_id}: {e}", exc_info=True
            )
            # Still remove the failure if recovery fails to avoid system getting stuck
            del active_failures[failure_id]


@app.route("/failures", methods=["GET"])
def list_failures():
    logger.info("Listing active failures")
    return jsonify(active_failures)


@app.route("/failures/<failure_id>", methods=["DELETE"])
def delete_failure(failure_id):
    logger.info(f"Request to remove failure: {failure_id}")

    with failure_lock:
        if failure_id not in active_failures:
            logger.warning(f"Failure {failure_id} not found")
            return jsonify({"error": "Failure not found"}), 404

        recover_failure(failure_id)
        return jsonify({"message": f"Failure {failure_id} recovered"})


@app.route("/health", methods=["GET"])
def health():
    logger.debug("Health check received")
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    logger.info("Starting server on port 5010")
    app.run(host="0.0.0.0", port=5010, debug=True)

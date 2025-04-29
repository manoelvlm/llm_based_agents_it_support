import logging

logger = logging.getLogger("chaos-engineering.cpu_overload")


def implement(container, intensity):
    """
    Implement CPU overload simulation on the target container.

    Args:
        container: Docker container object
        intensity: Level of intensity (low, medium, high)
    """
    logger.info(f"Implementing CPU overload with {intensity} intensity")

    # Fixa 2 núcleos para todas as intensidades
    cpu_count = 2

    # Map intensity to CPU load percentage
    cpu_load = 80  # Default for low - 80%
    if intensity == "medium":
        cpu_load = 85  # Medium - 85%
    elif intensity == "high":
        cpu_load = 90  # High - 90%

    logger.info(f"Starting CPU stress test with {cpu_count} cores at {cpu_load}% load")
    # Run stress-ng in background with specified intensity and load percentage
    stress_cmd = f"stress-ng --cpu {cpu_count} --cpu-load {cpu_load} --timeout 0 > /tmp/cpu-stress.log 2>&1 &"
    result = container.exec_run(f"bash -c '{stress_cmd}'", detach=True)
    logger.debug(f"CPU stress execution result: {result.exit_code}")


def recover(container):
    """
    Recover from CPU overload simulation.

    Args:
        container: Docker container object
    """
    logger.info("Terminating CPU stress processes in container")
    result = container.exec_run("pkill -9 -f stress-ng")
    logger.debug(f"pkill command result: {result.exit_code}")

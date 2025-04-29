import logging

logger = logging.getLogger("chaos-engineering.memory_leak")


def implement(container, intensity):
    """
    Implement memory leak simulation on the target container using stress-ng.

    Args:
        container: Docker container object
        intensity: Level of intensity (low, medium, high)
    """
    logger.info(f"Implementing memory leak with {intensity} intensity")

    # Map intensity to memory size to be consumed (in MB)
    memory_mb = 1700  # Default for low
    if intensity == "medium":
        memory_mb = 2100
    elif intensity == "high":
        memory_mb = 2200

    # Check if stress-ng is installed
    check_result = container.exec_run("which stress-ng")
    if check_result.exit_code != 0:
        logger.info("stress-ng not found, installing...")
        install_cmd = "apt-get update && apt-get install -y stress-ng"
        install_result = container.exec_run(install_cmd)
        if install_result.exit_code != 0:
            logger.error(
                f"Failed to install stress-ng: {install_result.output.decode('utf-8', errors='ignore')}"
            )
            raise Exception("Failed to install stress-ng")

    logger.info(f"Starting memory stress test consuming {memory_mb}MB")
    # Run stress-ng with VM stressor to simulate memory leak
    # --vm-bytes: amount of memory per VM process
    # --vm-keep: keep memory allocated
    # --vm 1: use 1 VM stressor
    # --vm-method zero-one: use a valid vm-method (alternating between 0 and 1 bit patterns)
    # --taskset 0: limit to first CPU core to minimize CPU impact
    stress_cmd = f"stress-ng --vm 1 --vm-bytes {memory_mb}M --vm-keep --vm-method zero-one --taskset 0 --timeout 0 > /tmp/memory-stress.log 2>&1 &"
    result = container.exec_run(f"bash -c '{stress_cmd}'", detach=True)
    logger.debug(f"Memory stress execution result: {result.exit_code}")

    # Verify the process is running
    import time

    time.sleep(1)
    check = container.exec_run("ps aux | grep stress-ng | grep -v grep")
    logger.debug(
        f"Process verification: {check.output.decode('utf-8', errors='ignore')}"
    )


def recover(container):
    """
    Recover from memory leak simulation.

    Args:
        container: Docker container object
    """
    logger.info("Terminating memory stress processes in container")
    result = container.exec_run("pkill -9 -f 'stress-ng --vm'")
    logger.debug(f"pkill command result: {result.exit_code}")

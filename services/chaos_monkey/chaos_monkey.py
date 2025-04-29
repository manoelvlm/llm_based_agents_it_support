# chaos_monkey.py
import logging
import random
import time

import requests
import schedule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chaos-monkey")

FAILURE_CONTROLLER_URL = "http://failure-controller:5010/failures"
SERVICES = ["user-service"]

# FAILURE_TYPES = {
#     "hardware": ["cpu_overload", "memory_leak"],
# }

FAILURE_TYPES = {
    "hardware": ["cpu_overload"],
}

CATEGORY_WEIGHTS = {
    "hardware": 1.0,  # 100% weight since it's the only category
}


def create_random_failure():
    """Create a random hardware failure on a random service"""
    service = random.choice(SERVICES)

    # Always select hardware since it's our only category
    category = "hardware"
    failure_type = random.choice(FAILURE_TYPES[category])
    intensity = random.choice(["low", "medium", "high"])

    # Set duration for hardware failures
    duration = random.randint(1200, 1500)  # 20-25 minutes

    logger.info(
        f"Creating {category} failure: {failure_type} on {service} with {intensity} intensity"
    )

    try:
        response = requests.post(
            FAILURE_CONTROLLER_URL,
            json={
                "type": failure_type,
                "service": service,
                "duration": duration,
                "intensity": intensity,
            },
        )

        if response.status_code == 201:
            logger.info(f"Failure created successfully: {response.json()}")
        else:
            logger.error(f"Failed to create failure: {response.text}")

    except Exception as e:
        logger.error(f"Error creating failure: {str(e)}")


# Schedule to run every x minutes
schedule.every(2).minutes.do(create_random_failure)

if __name__ == "__main__":
    logger.info("Chaos Monkey started")

    # Run first chaos event after short initial delay
    logger.info("Scheduling first chaos event in 15 seconds...")
    time.sleep(15)
    create_random_failure()

    # Continue with regular schedule
    while True:
        schedule.run_pending()
        time.sleep(60)

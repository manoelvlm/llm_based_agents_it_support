import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import psutil

# Setup logging
logging.basicConfig(
    filename="/var/log/diagnostics/service_monitor.log",
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
)


class PythonServiceMonitor:
    def __init__(self, service_name="user_service", monitor_interval=60):
        self.service_name = service_name
        self.monitor_interval = monitor_interval
        self.output_dir = Path("/opt/diagnostics/reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def find_python_process(self):
        """Find the Python process running the service."""
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            if proc.info["name"] == "python3" and any(
                self.service_name in cmd for cmd in proc.info["cmdline"] if cmd
            ):
                return proc
        return None

    def collect_process_info(self, process):
        """Collect detailed information about the process."""
        if not process:
            return None

        try:
            # Basic process info
            info = {
                "timestamp": datetime.now().isoformat(),
                "pid": process.pid,
                "status": process.status(),
                "cpu_percent": process.cpu_percent(interval=1.0),
                "memory_info": {
                    "rss": process.memory_info().rss / (1024 * 1024),  # MB
                    "vms": process.memory_info().vms / (1024 * 1024),  # MB
                },
                "create_time": datetime.fromtimestamp(
                    process.create_time()
                ).isoformat(),
                "threads": len(process.threads()),
                "open_files": len(process.open_files()),
                "connections": [c._asdict() for c in process.connections()],
            }

            # Add thread information
            thread_info = []
            for thread in process.threads():
                thread_info.append(
                    {
                        "id": thread.id,
                        "user_time": thread.user_time,
                        "system_time": thread.system_time,
                    }
                )
            info["thread_details"] = thread_info

            return info
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logging.error(f"Error collecting process info: {e}")
            return None

    def write_report(self, info):
        """Write the process information to a JSON file."""
        if not info:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"{self.service_name}_monitor_{timestamp}.json"

        try:
            with open(filename, "w") as f:
                json.dump(info, f, indent=2)
            logging.info(f"Wrote monitoring report to {filename}")
        except Exception as e:
            logging.error(f"Error writing monitoring report: {e}")

    def monitor_once(self):
        """Run a single monitoring cycle."""
        process = self.find_python_process()
        if not process:
            logging.warning(f"Could not find process for {self.service_name}")
            return

        info = self.collect_process_info(process)
        self.write_report(info)
        return info

    def monitor_continuously(self):
        """Monitor the service at regular intervals."""
        logging.info(
            f"Starting continuous monitoring of {self.service_name} every {self.monitor_interval} seconds"
        )

        try:
            while True:
                self.monitor_once()
                time.sleep(self.monitor_interval)
        except KeyboardInterrupt:
            logging.info("Monitoring stopped by user")
        except Exception as e:
            logging.error(f"Monitoring error: {e}")


if __name__ == "__main__":
    monitor = PythonServiceMonitor()
    monitor.monitor_continuously()

#!/usr/bin/env python3
"""
Helper script to check and debug log files
"""
import os
import sys
from datetime import datetime


def check_log_file(path):
    """Check if log file exists and print its stats"""
    print(f"\nChecking log file: {path}")

    if not os.path.exists(path):
        print(f"  ERROR: File does not exist")
        return False

    try:
        stats = os.stat(path)
        print(f"  Size: {stats.st_size} bytes")
        print(f"  Last modified: {datetime.fromtimestamp(stats.st_mtime)}")
        print(f"  Permissions: {oct(stats.st_mode)[-3:]}")

        # Check if readable
        with open(path, "r") as f:
            lines = f.readlines()
            print(f"  Line count: {len(lines)}")
            if lines:
                print(f"  First line: {lines[0].strip()}")
                print(f"  Last line: {lines[-1].strip()}")
        return True
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        return False


def main():
    """Main function"""
    log_files = [
        "/var/log/app/application.log",
        "/var/log/app/errors.log",
        "/var/log/app/access.log",
        "/app/app.log",
        "/app/error.log",
    ]

    print("=== LOG FILE DIAGNOSTICS ===")

    for log_file in log_files:
        check_log_file(log_file)

    print("\n=== LOG DIRECTORY PERMISSIONS ===")
    log_dirs = ["/var/log/app", "/app"]
    for dir_path in log_dirs:
        try:
            print(f"Directory: {dir_path}")
            if os.path.exists(dir_path):
                print(f"  Exists: Yes")
                print(f"  Permissions: {oct(os.stat(dir_path).st_mode)[-3:]}")
                print(f"  Contents: {os.listdir(dir_path)}")
            else:
                print(f"  Exists: No")
        except Exception as e:
            print(f"  ERROR: {str(e)}")

    print("\n=== WRITING TEST LOG ===")
    test_log = "/app/test_log.txt"
    try:
        with open(test_log, "w") as f:
            f.write(f"Test log entry at {datetime.now()}\n")
        print(f"Successfully wrote to {test_log}")
    except Exception as e:
        print(f"Failed to write to {test_log}: {str(e)}")


if __name__ == "__main__":
    main()

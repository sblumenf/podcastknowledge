"""
Mock psutil module for when the real psutil is not available.

This provides basic functionality to prevent import errors.
"""

class MockProcess:
    """Mock Process class."""
    def __init__(self, pid=None):
        self.pid = pid or os.getpid()
    
    def memory_info(self):
        """Mock memory info."""
        class MemInfo:
            rss = 100 * 1024 * 1024  # 100MB default
        return MemInfo()
    
    def cpu_percent(self, interval=None):
        """Mock CPU percent."""
        return 10.0  # 10% default


class MockMemory:
    """Mock virtual memory."""
    total = 8 * 1024 * 1024 * 1024  # 8GB
    available = 4 * 1024 * 1024 * 1024  # 4GB
    percent = 50.0
    used = 4 * 1024 * 1024 * 1024  # 4GB
    free = 4 * 1024 * 1024 * 1024  # 4GB


class MockDisk:
    """Mock disk usage."""
    total = 500 * 1024 * 1024 * 1024  # 500GB
    used = 250 * 1024 * 1024 * 1024  # 250GB
    free = 250 * 1024 * 1024 * 1024  # 250GB
    percent = 50.0


def Process(pid=None):
    """Mock Process factory."""
    return MockProcess(pid)


def virtual_memory():
    """Mock virtual memory."""
    return MockMemory()


def disk_usage(path='/'):
    """Mock disk usage."""
    return MockDisk()


def cpu_percent(interval=None, percpu=False):
    """Mock CPU percent."""
    if percpu:
        return [10.0, 15.0, 20.0, 25.0]  # Mock 4 cores
    return 20.0  # 20% overall


def cpu_count(logical=True):
    """Mock CPU count."""
    return 4  # Default to 4 cores


# For compatibility
net_io_counters = lambda: None
disk_io_counters = lambda: None

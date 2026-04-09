"""
Cross-platform file locking for Agency OS JSON stores.

Prevents race conditions when multiple processes (webhook server, scheduler
daemon, pipeline subprocess) read/write the same JSON files concurrently.
"""

import os
from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None


@contextmanager
def file_lock(path: str, *, shared: bool = False):
    """
    Acquire a file-level lock for safe concurrent access.

    Args:
        path: Path to the file to lock. A .lock file is created alongside it.
        shared: If True, acquire a shared (read) lock. If False, acquire an
                exclusive (write) lock.

    Usage:
        with file_lock("schedule.json"):
            data = json.load(open("schedule.json"))
            data.append(new_item)
            json.dump(data, open("schedule.json", "w"))
    """
    lock_path = path + ".lock"
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w")
        if fcntl:
            lock_type = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            fcntl.flock(lock_fd.fileno(), lock_type)
        elif msvcrt:
            # msvcrt locking blocks on Windows if already locked
            # It acquires an exclusive lock on the first 1 byte
            import time
            while True:
                try:
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        yield
    finally:
        if lock_fd is not None:
            try:
                if fcntl:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                elif msvcrt:
                    # Windows expects unlocking exactly what was locked
                    lock_fd.seek(0)
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            try:
                lock_fd.close()
            except Exception:
                pass

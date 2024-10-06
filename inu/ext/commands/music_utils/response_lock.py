from typing import *
from datetime import datetime, timedelta

import asyncio


class ResponseLock:
    """
    A Lock to prevent the MusicPlayer to send 2 responses whithin a short time interval.
    """
    def __init__(self, minimum_delay: timedelta) -> None:
        self._minimum_delay: timedelta = minimum_delay
        self._last_response: datetime = datetime(2000, 1, 1)
        
    def is_available(self) -> bool:
        """
        Wheter or not the lock is available.
        """
        return datetime.now() - self._last_response >= self._minimum_delay
    
    def lock(self) -> bool:
        """
        Lock the lock.
        
        Returns:
            bool: Wheter or not the lock was locked.
        """
        if not self.is_available():
            return False
        self._last_response = datetime.now()
        return True
        
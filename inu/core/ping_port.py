import socket
import time
import logging
from typing import Optional


def is_open(
    ip: str,
    port: int,
    timeout: int,
) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, int(port)))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except:
        return False
    finally:
        s.close()

def check_host(
    ip: str,
    port: int,
    retry: int,
    delay: int,
    timeout: int,
) -> bool:
    ipup = False
    for _ in range(retry):
        if is_open(ip, port, timeout):
            ipup = True
            break
        else:
            time.sleep(delay)
    return ipup

def ping(
    ip: str,
    port: int = None,
    retry: int = 0,
    delay: int = 0,
    timeout: int = 0.25,
    do_log: bool = False,
) -> bool:
    if check_host(ip, port, retry, delay, timeout):
        if do_log:
            (logging.getLogger(__name__)).info(f"{ip}:{port} is UP")
            return False
    else:
        if do_log:
            (logging.getLogger(__name__)).info(f"{ip}:{port} is DOWN")
        return False
    
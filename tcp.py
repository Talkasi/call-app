import logging
import socket as s

log = None


def init():
    global log

    assert not log

    log = logging.getLogger('TCP')


def get_host_port(addr: str) -> (str, int):
    addr_parts = addr.split(":")
    assert len(addr_parts) == 2

    return addr_parts[0], int(addr_parts[1])


def listen(addr="127.0.0.1:1234"):
    sock = s.socket(s.AF_INET, s.SOCK_STREAM)
    sock.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR, 1)
    sock.bind(get_host_port(addr))
    sock.listen()

    log.info(f"Listening on {addr}")
    return sock


def dial(addr="127.0.0.1:1234"):
    sock = s.socket(s.AF_INET, s.SOCK_STREAM)

    log.info(f"Dialing {addr}...")
    sock.connect(get_host_port(addr))
    log.info(f"Connected to {addr}")

    return sock

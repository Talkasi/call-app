import socket
import logging

log = None


def init():
    global log

    assert not log

    log = logging.getLogger("UDP")


def get_host_port(addr: str) -> (str, int):
    addr_parts = addr.split(":")
    if len(addr_parts) == 1:
        # NOTE: adding default port value.
        addr_parts.append(str(4321))
    assert len(addr_parts) == 2

    return addr_parts[0], int(addr_parts[1])


def get_addr(host: str, port: int) -> str:
    return ':'.join((host, str(port)))


def listen(addr="127.0.0.1:4321"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # NOTE: going back and forth to add port if missing.
    host, port = get_host_port(addr)
    addr = get_addr(host, port)

    sock.bind((host, port))

    log.info(f"Listening on {addr}")
    return sock


def dial(addr="127.0.0.1:4321"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # NOTE: going back and forth to add port if missing.
    host, port = get_host_port(addr)
    addr = get_addr(host, port)

    log.info(f"Dialing {addr}...")
    sock.connect((host, port))
    log.info(f"Connected to {addr}")

    return sock

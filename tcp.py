import logging
import socket as s

log = None


def init():
    global log

    assert not log

    log = logging.getLogger("TCP")


def get_host_port(addr: str) -> (str, int):
    addr_parts = addr.split(":")
    if len(addr_parts) == 1:
        # NOTE: adding default port value.
        addr_parts.append(str(1234))
    assert len(addr_parts) == 2

    return addr_parts[0], int(addr_parts[1])


def get_addr(host: str, port: int) -> str:
    return ':'.join((host, str(port)))


def listen(host="127.0.0.1", port=1234):
    sock = s.socket(s.AF_INET, s.SOCK_STREAM)
    sock.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR, 1)

    # NOTE: going back and forth to add port if missing.
    # host, port = get_host_port(addr)
    # addr = get_addr(host, port)

    sock.bind((host, port))
    sock.listen()

    log.info(f"Listening on {host + ':' + str(port)}")
    return sock


def dial(host="127.0.0.1", port=1234):
    sock = s.socket(s.AF_INET, s.SOCK_STREAM)

    # NOTE: going back and forth to add port if missing.
    # host, port = get_host_port(addr)
    # addr = get_addr(host, port)

    log.info(f"Dialing {host + ':' + str(port)}...")
    sock.connect((host, port))
    log.info(f"Connected to {host + ':' + str(port)}")

    return sock

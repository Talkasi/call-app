import socket
import logging

log = None


def init():
    global log

    assert not log

    log = logging.getLogger("UDP")


def listen(host="127.0.0.1", port=4321):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    sock.bind((host, port))

    log.info(f"Listening on {host + ':' + str(port)}")
    return sock


def dial(host="127.0.0.1", port=4321):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    log.info(f"Dialing {host + ':' + str(port)}...")
    sock.connect((host, port))
    log.info(f"Connected to {host + ':' + str(port)}")

    return sock

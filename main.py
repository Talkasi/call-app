import argparse
import logger
import logging
import os
import sound as snd
import tcp

from threading import Thread


def read_send(sock):
    try:
        while True:
            # NOTE: from the documentation:
            # > nframes parameter is not constrained to a specific range,
            # > however high performance applications will want to
            # > match this parameter to the blocksize parameter used
            # > when opening the stream.
            samples = snd.read_from_device(snd.instream.blocksize)
            sock.send(samples)
            logger.root_logger.debug(f"Read and sent {len(samples)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_play(sock):
    try:
        while True:
            samples = sock.recv(snd.outstream.blocksize)
            snd.write_to_device(samples)
            logger.root_logger.debug(
                f"Received and played {len(samples)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def start_threads(sock):
    read_send_thread = Thread(target=read_send, args=(sock, ))
    receive_play_thread = Thread(target=receive_play, args=(sock, ))

    read_send_thread.start()
    receive_play_thread.start()

    read_send_thread.join()
    receive_play_thread.join()


def server(addr):
    sock = tcp.listen(addr)

    while True:
        peer_sock, (peer_host, peer_port) = sock.accept()
        peer_addr = tcp.get_addr(peer_host, peer_port)
        tcp.log.info(f"Accepted from {peer_addr}")

        start_threads(peer_sock)


def client(addr):
    sock = tcp.dial(addr)
    start_threads(sock)


def main():
    argparser = argparse.ArgumentParser(prog="call-app",
                                        description="Google Meet replacement.")
    argparser.add_argument("addr", help="address to work with")
    argparser.add_argument(
        "-l",
        "--listen",
        action="store_const",
        dest="handler",
        default=client,
        const=server,
        help="listen on the specified address instead of making connection")
    argparser.add_argument('-v',
                           '--verbose',
                           action='store_true',
                           help="enable debug logs")
    args = argparser.parse_args()

    logger.init(args.verbose)
    snd.init()
    tcp.init()

    # NOTE: calling server or client function depending on provided arguments.
    try:
        args.handler(args.addr)
    except (ConnectionRefusedError, OSError) as e:
        logger.root_logger.fatal(e)


if __name__ == "__main__":
    main()

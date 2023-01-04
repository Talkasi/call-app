import argparse
import logger
import sound as snd
import tcp

from threading import Thread

buffer_size = None


def read_send(sock):
    try:
        while True:
            # NOTE: from the documentation:
            # > nframes parameter is not constrained to a specific range,
            # > however high performance applications will want to
            # > match this parameter to the blocksize parameter used
            # > when opening the stream.
            samples = b""
            while len(samples) < buffer_size:
                samples += snd.read_from_device(snd.instream.blocksize)

            sent = 0
            while sent < len(samples):
                sent += sock.send(samples[sent:])

            logger.root_logger.debug(f"Read and sent {len(samples)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_play(sock):
    try:
        while True:
            samples = b""
            while len(samples) < snd.outstream.blocksize:
                received = sock.recv(buffer_size - len(samples))
                samples += received

            snd.write_to_device(samples)

            logger.root_logger.debug(
                f"Received and played {len(samples)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def start_join_threads(sock):
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

        start_join_threads(peer_sock)


def client(addr):
    sock = tcp.dial(addr)
    start_join_threads(sock)


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
    argparser.add_argument("-v",
                           "--verbose",
                           action="store_true",
                           help="enable debug logs")
    args = argparser.parse_args()

    logger.init(args.verbose)
    snd.init()
    tcp.init()

    global buffer_size
    buffer_size = snd.instream.blocksize * 2 * 10  # NOTE: 10 kiB

    # NOTE: calling server or client function depending on provided arguments.
    try:
        args.handler(args.addr)
    except (ConnectionRefusedError, OSError) as e:
        logger.root_logger.fatal(e)


if __name__ == "__main__":
    main()

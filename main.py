import logger
import os
import sound as snd
import tcp

from threading import Thread


def read_send(sock):
    while True:
        # NOTE: from the documentation:
        # > nframes parameter is not constrained to a specific range,
        # > however high performance applications will want to
        # > match this parameter to the blocksize parameter used
        # > when opening the stream.
        samples = snd.read_from_device(snd.instream.blocksize)
        sock.send(samples)
        logger.root_logger.debug(f"Read and sent {len(samples)} bytes")


def receive_play(sock):
    while True:
        samples = sock.recv(snd.outstream.blocksize)
        snd.write_to_device(samples)
        logger.root_logger.debug(f"Received and played {len(samples)} bytes")


def main():
    logger.init()
    snd.init()
    tcp.init()

    # TODO: probably move this to some other place.
    if os.getenv("SERVER"):
        sock = tcp.listen()
        sock, peer = sock.accept()
        tcp.log.info(f"Accepted from {peer}")
    elif os.getenv("CLIENT"):
        sock = tcp.dial()
    else:
        logger.root_logger.fatal(
            "cannot proceed without role; specify 'SERVER' or 'CLIENT'.")
        exit(1)

    read_send_thread = Thread(target=read_send, args=(sock, ))
    receive_play_thread = Thread(target=receive_play, args=(sock, ))

    read_send_thread.start()
    receive_play_thread.start()

    read_send_thread.join()
    receive_play_thread.join()


if __name__ == "__main__":
    main()

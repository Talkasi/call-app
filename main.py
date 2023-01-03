import logger
import os
import sound as snd
import tcp

if __name__ == "__main__":
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

    while True:
        # NOTE: from the documentation:
        # > nframes parameter is not constrained to a specific range,
        # > however high performance applications will want to
        # > match this parameter to the blocksize parameter used
        # > when opening the stream.

        # TODO: make read and write for both
        if os.getenv("SERVER"):
            samples = snd.read_from_device(snd.instream.blocksize)
            sock.send(samples)
        else:
            samples = sock.recv(snd.outstream.blocksize)
            snd.write_to_device(samples)

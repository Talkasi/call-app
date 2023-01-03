import logger
import sound as snd
import time

if __name__ == "__main__":
    logger.init()
    snd.init()

    while True:
        # NOTE: from the documentation:
        # > nframes parameter is not constrained to a specific range,
        # > however high performance applications will want to
        # > match this parameter to the blocksize parameter used
        # > when opening the stream.
        samples = snd.read_from_device(snd.instream.blocksize)
        snd.write_to_device(samples)

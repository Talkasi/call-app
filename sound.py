import logging
import sounddevice as sd

# NOTE: following must be initialized before using!
# Call `init()` for that.
instream = None
outstream = None
log = None


def init(channels: int = 1, blocksize: int = 256):
    global instream
    global outstream
    global log

    instream = sd.RawInputStream(blocksize=blocksize, channels=channels)
    outstream = sd.RawOutputStream(samplerate=instream.samplerate,
                                   blocksize=blocksize,
                                   channels=channels)

    log = logging.getLogger("Microphone")


def read_from_device(nframes=None):
    """
NOTE: read_from_device reads all available samples from the microphone
and returns them as a Python `buffer` object.
Calling it without specifying `nframes` will make this function non-blocking.
    """
    assert instream
    assert log

    if instream.stopped:
        instream.start()

    to_read = nframes if nframes else instream.read_available

    data, overflowed = instream.read(to_read)
    if overflowed:
        log.warning(
            f"input sound device overflowed; read {len(data)} bytes total")
    return data


def write_to_device(samples) -> None:
    assert outstream
    assert log

    if outstream.stopped:
        outstream.start()

    underflowed = outstream.write(samples)
    if underflowed:
        log.warning(f"output sound device underflowed")

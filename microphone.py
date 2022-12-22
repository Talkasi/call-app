import queue
import threading

import sounddevice as sd

q = queue.Queue()
event = threading.Event()


# NOTE: prototype of this callback is specified at
# https://python-sounddevice.readthedocs.io/en/latest/api/raw-streams.html#sounddevice.RawOutputStream
def outstream_callback(outdata, frames, time, status) -> None:
    if status.output_underflow:
        raise sd.CallbackAbort
    assert not status
    try:
        data = q.get_nowait()
    except queue.Empty as e:
        raise sd.CallbackAbort from e
    if len(data) < len(outdata):
        outdata[:len(data)] = data
        outdata[len(data):] = b'\x00' * (len(outdata) - len(data))
        raise sd.CallbackStop
    else:
        outdata[:] = data


def loopback(channels: int = 1,
             blocksize: int = 64,
             buffersize: int = 32) -> None:
    with sd.RawInputStream(blocksize=blocksize, channels=channels) as instream:
        # NOTE: pre-fill the queue
        for _ in range(buffersize):
            data, _ = instream.read(blocksize)
            if not data:
                break
            q.put_nowait(data)

        with sd.RawOutputStream(samplerate=instream.samplerate,
                                blocksize=blocksize,
                                channels=channels,
                                callback=outstream_callback,
                                finished_callback=event.set) as outstream:
            timeout = blocksize * buffersize / instream.samplerate
            while True:
                data, _ = instream.read(blocksize)
                if not data:
                    break
                q.put(data, timeout=timeout)
            event.wait()  # NOTE: wait until playback is finished

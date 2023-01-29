import argparse
import logging
import math
import time
from io import BytesIO
from PIL import Image
import logger
import sound as snd
import pygame.image
import camera
import tcp
import udp
import struct
from threading import Thread

BUFFER_SIZE = None
INFORMATION_SIZE = struct.calcsize("i" * 3)
CHUNK_SIZE = 1500 - INFORMATION_SIZE


def get_send_video(sock, resolution=(640, 480)):
    sock.settimeout(100)
    cam = camera.camera_init()

    current_image_number = 0
    try:
        while True:
            while not cam.query_image():
                pass
            camera_image = cam.get_image()

            buffer = BytesIO()
            im = Image.frombuffer("RGB", resolution, bytes(pygame.image.tostring(camera_image, "RGB")))
            # NOTE: quality parameter was chosen experimentally
            im.save(buffer, optimize=True, quality=45, format='JPEG')
            image = buffer.getvalue()

            # To prevent integer overflow in bytes sending
            if current_image_number == 2 ** 32 - 1:
                current_image_number = 0

            for i in range(int(math.ceil(len(image) / CHUNK_SIZE))):
                sock.send(b''.join([struct.pack('iii', len(image),  current_image_number, i),
                                    image[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]]))

            current_image_number += 1
            logger.root_logger.debug(f"Camera. Got and sent {len(image)} bytes")
            time.sleep(0)

    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_send_video(sock, queue=b'', resolution=(640, 480)):
    log = logging.getLogger("Camera")
    pygame.display.set_caption("call-app")
    window_display = pygame.display.set_mode(resolution)

    current_image_number = 0
    try:
        while True:
            if len(queue) != 0:
                data = [queue]
            else:
                data = []

            # To prevent integer overflow in bytes sending
            if current_image_number == 2 ** 32 - 1:
                current_image_number = 0

            while True:
                try:
                    pack = sock.recv(CHUNK_SIZE + INFORMATION_SIZE)
                    pack_number = struct.unpack('i', pack[4:8])[0]
                    while pack_number < current_image_number:
                        pack = sock.recv(CHUNK_SIZE + INFORMATION_SIZE)
                        pack_number = struct.unpack('i', pack[4:8])[0]
                    if pack_number == current_image_number:
                        data += [pack]
                    if pack_number > current_image_number:
                        queue = pack
                        break
                except TimeoutError:
                    pass

            current_image_number += 1

            data = list(set(data))
            data.sort(key=lambda data_item: struct.unpack('i', data_item[8:12])[0])

            image = b''
            error_key = 0
            index_should_be = 0
            for i in range(len(data)):
                data_index = struct.unpack('i', data[i][8:12])[0]
                if data_index - index_should_be > 0:
                    error_key = 1
                    break

                image += data[i][12:]
                index_should_be += 1

            if struct.unpack('i', data[0][:4])[0] - len(image) > 0 or error_key:
                log.warning("File corrupted")
                time.sleep(0)
                continue

            try:
                buffer = BytesIO(image)
                image = Image.open(buffer).tobytes()

                camera_image = pygame.image.fromstring(image, resolution, 'RGB')
                if camera.camera_print_image(camera_image, window_display) == 0:
                    return
                log.debug(f"Received and played {sum(len(pack) for pack in data)} bytes")
            except:
                log.warning("File corrupted")

            time.sleep(0)

    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def read_send_sound(sock):
    log = logging.getLogger("Sound")
    try:
        while True:
            # NOTE: from the documentation:
            # > nframes parameter is not constrained to a specific range,
            # > however high performance applications will want to
            # > match this parameter to the blocksize parameter used
            # > when opening the stream.
            samples = b''
            while len(samples) < BUFFER_SIZE:
                samples += snd.read_from_device(snd.instream.blocksize)

            sent = 0
            while sent < len(samples):
                sent += sock.send(samples[sent:])

            log.debug(f"Read and sent {len(samples)} bytes")
            time.sleep(0)

    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)



def receive_play_sound(sock):
    log = logging.getLogger("Sound")
    try:
        while True:
            samples = b''
            while len(samples) < BUFFER_SIZE:
                samples += sock.recv(BUFFER_SIZE - len(samples))

            snd.write_to_device(samples)

            log.debug(f"Sound. Received and played {len(samples)} bytes")
            time.sleep(0)

    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def start_join_threads(sock_tcp, sock_udp, pack=b''):
    read_send_sound_thread = Thread(target=read_send_sound, args=(sock_tcp,))
    receive_play_sound_thread = Thread(target=receive_play_sound, args=(sock_tcp,))
    get_and_send_video_thread = Thread(target=get_send_video, args=(sock_udp,))
    receive_and_play_video_thread = Thread(target=receive_send_video, args=(sock_udp, pack,))

    read_send_sound_thread.start()
    receive_play_sound_thread.start()
    get_and_send_video_thread.start()
    receive_and_play_video_thread.start()

    read_send_sound_thread.join()
    receive_play_sound_thread.join()
    get_and_send_video_thread.join()
    receive_and_play_video_thread.join()

    # NOTE: stop steams so no further data is buffered.
    # They will be started back automatically after first read.
    snd.instream.stop()
    snd.outstream.stop()


def server(addr):
    sock_tcp = tcp.listen(addr)

    host = addr.split(':')[0]
    sock_udp = udp.listen(host, 4321)

    while True:
        peer_sock_tcp, (peer_host_tcp, peer_port_tcp) = sock_tcp.accept()
        peer_addr_tcp = tcp.get_addr(peer_host_tcp, peer_port_tcp)
        tcp.log.info(f"Accepted from {peer_addr_tcp}")

        data_received, address = sock_udp.recvfrom(CHUNK_SIZE + 12)
        sock_udp.connect(address)
        udp.log.info(f"Connected to {address[0] + ':' + str(address[1])}")

        start_join_threads(peer_sock_tcp, sock_udp, data_received)


def client(addr):
    sock_tcp = tcp.dial(addr)
    host = addr.split(':')[0]
    sock_udp = udp.dial(host, 4321)
    start_join_threads(sock_tcp, sock_udp)


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
    udp.init()

    global BUFFER_SIZE
    BUFFER_SIZE = snd.instream.blocksize * 2 * 4  # NOTE: 4 kiB

    # NOTE: calling server or client function depending on provided arguments.
    try:
        args.handler(args.addr)
    except (ConnectionRefusedError, OSError) as e:
        logger.root_logger.fatal(e)


if __name__ == "__main__":
    main()

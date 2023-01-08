import argparse
import logger
import sound as snd
import pygame.image
import camera
import tcp
import udp
import struct
from threading import Thread

buffer_size = None
CHUNK_SIZE = 51200


def get_and_send_data(sock):
    cam = camera.camera_init()

    try:
        while True:
            camera_image = cam.get_image()
            data = pygame.image.tostring(camera_image, 'RGB')

            for i in range(640 * 480 * 3 // CHUNK_SIZE):
                sock.send(b''.join([struct.pack("i", i), data[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]]))

            logger.root_logger.debug(f"Camera. Got and sent {len(data)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_and_play_data(sock, pack=b'', resolution=(640, 480)):
    window_display = pygame.display.set_mode(resolution)

    try:
        while True:
            data = []
            index = []

            if len(pack) != 0:
                if len(pack) != CHUNK_SIZE + 1:
                    pack = pack + b'\x00' * (CHUNK_SIZE + 1 - len(pack))

                index.append(pack[0])
                data.append(pack)
                pack = b''

            while len(data) < resolution[0] * resolution[1] * 3 // CHUNK_SIZE:  # Size of an image // size of the record
                got = sock.recv(CHUNK_SIZE + 1)

                if got[0] in index:
                    continue

                index.append(got[0])
                if len(got) != CHUNK_SIZE + 1:
                    got = got + b'\x00' * (CHUNK_SIZE + 1 - len(got))

                data.append(got)

            data = sorted(data, key=lambda data_item: data_item[0])

            image = b''
            for i in range(len(data)):
                image += bytes(data[i][1:])

            camera_image = pygame.image.fromstring(image, resolution, 'RGB')
            if camera.camera_print_image(camera_image, window_display) == 0:
                return

            logger.root_logger.debug(f"Camera. Received and played {len(image)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def read_send(sock):
    try:
        while True:
            # NOTE: from the documentation:
            # > nframes parameter is not constrained to a specific range,
            # > however high performance applications will want to
            # > match this parameter to the blocksize parameter used
            # > when opening the stream.
            samples = b''
            while len(samples) < buffer_size:
                samples += snd.read_from_device(snd.instream.blocksize)

            sent = 0
            while sent < len(samples):
                sent += sock.send(samples[sent:])

            logger.root_logger.debug(f"Sound. Read and sent {len(samples)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_play(sock):
    try:
        while True:
            samples = b''
            while len(samples) < buffer_size:
                samples += sock.recv(buffer_size - len(samples))

            snd.write_to_device(samples)

            logger.root_logger.debug(
                f"Sound. Received and played {len(samples)} bytes")

    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def start_join_threads(sock_tcp, sock_udp, pack=b''):
    read_send_thread = Thread(target=read_send, args=(sock_tcp,))
    receive_play_thread = Thread(target=receive_play, args=(sock_tcp,))
    get_and_send_thread = Thread(target=get_and_send_data, args=(sock_udp,))
    receive_and_play_thread = Thread(target=receive_and_play_data, args=(sock_udp, pack, ))

    read_send_thread.start()
    receive_play_thread.start()
    get_and_send_thread.start()
    receive_and_play_thread.start()

    read_send_thread.join()
    receive_play_thread.join()
    get_and_send_thread.join()
    receive_and_play_thread.join()

    # NOTE: stop steams so no further data is buffered.
    # They will be started back automatically after first read.
    snd.instream.stop()
    snd.outstream.stop()


def server(addr):
    sock_tcp = tcp.listen(addr)
    sock_udp = udp.listen(addr)

    while True:
        peer_sock_tcp, (peer_host_tcp, peer_port_tcp) = sock_tcp.accept()
        peer_addr_tcp = tcp.get_addr(peer_host_tcp, peer_port_tcp)
        tcp.log.info(f"Accepted from {peer_addr_tcp}")

        data_received, address = sock_udp.recvfrom(CHUNK_SIZE)
        sock_udp.connect(address)

        start_join_threads(peer_sock_tcp, sock_udp, data_received)


def client(addr):
    sock_tcp = tcp.dial(addr)
    sock_udp = udp.dial(addr)

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

    global buffer_size
    buffer_size = snd.instream.blocksize * 2 * 4  # NOTE: 4 kiB

    # NOTE: calling server or client function depending on provided arguments.
    try:
        args.handler(args.addr)
    except (ConnectionRefusedError, OSError) as e:
        logger.root_logger.fatal(e)


if __name__ == "__main__":
    main()

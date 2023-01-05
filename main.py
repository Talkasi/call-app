import argparse
import sound as snd
import tcp
import udp

import logger
import struct
import pygame.image
import camera
import gzip
from threading import Thread

buffer_size = None


UDP_IP = "127.0.0.1"
UDP_PORT = 8080
MAX_PACK = 65507


def get_and_send_data(sock):
    cam = camera.camera_init()

    try:
        while True:
            camera_image = cam.get_image()

            data = pygame.image.tostring(camera_image, 'RGB')
            data = gzip.compress(bytes(list(data)))

            # Send size of data to receive
            sock.send(struct.pack("i", len(data)))

            sent_size = 0
            while sent_size < len(data):
                size_to_send = MAX_PACK if len(data) - sent_size > MAX_PACK else len(data) - sent_size

                sock.send(data[sent_size:sent_size + size_to_send])
                sent_size += size_to_send

            if sent_size > len(data):
                print("[!]Error in sending.")
                exit(1)

            logger.root_logger.debug(f"Read and sent {len(data)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_and_play_data(sock, resolution=(1280, 720)):
    window_display = pygame.display.set_mode(resolution)
    try:
        while True:
            size = int(sock.recv(4).decode("ascii"))

            size_received = 0
            data = b""
            while size_received < size:
                data = sock.recv(size)
                size_to_receive = MAX_PACK if len(data) - size_received > MAX_PACK else len(data) - size_received

                data += sock.recv(size_to_receive)

            if size_received != size:
                print("[!]Error in receiving.")
                exit(1)

            data = gzip.decompress(data).decode("ascii")

            camera_image = pygame.image.fromstring(data, resolution, 'RGB')

            if camera.camera_print_image(camera_image, window_display) == 0:
                return

            logger.root_logger.debug(f"Read and sent {len(data)} bytes")
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
            while len(samples) < buffer_size:
                samples += sock.recv(buffer_size - len(samples))

            snd.write_to_device(samples)

            logger.root_logger.debug(
                f"Received and played {len(samples)} bytes")

    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def start_join_threads(sock):
    read_send_thread = Thread(target=read_send, args=(sock, ))
    receive_play_thread = Thread(target=receive_play, args=(sock, ))
    receive_and_play_thread = Thread(target=receive_and_play_data, args=(sock, ))
    get_and_send_thread = Thread(target=get_and_send_data, args=(sock,))

    read_send_thread.start()
    receive_play_thread.start()
    receive_and_play_thread.start()
    get_and_send_thread.start()

    read_send_thread.join()
    receive_play_thread.join()
    receive_and_play_thread.join()
    get_and_send_thread.join()

    # NOTE: stop steams so no further data is buffered.
    # They will be started back automatically after first read.
    snd.instream.stop()
    snd.outstream.stop()


def tcp_server(addr):
    sock = tcp.listen(addr)

    while True:
        peer_sock, (peer_host, peer_port) = sock.accept()
        peer_addr = tcp.get_addr(peer_host, peer_port)
        tcp.log.info(f"Accepted from {peer_addr}")

        start_join_threads(peer_sock)


def tcp_client(addr):
    sock = tcp.dial(addr)
    start_join_threads(sock)


def udp_server(addr):
    sock = udp.listen(addr)

    while True:
        peer_sock, (peer_host, peer_port) = sock.accept()
        peer_addr = udp.get_addr(peer_host, peer_port)
        udp.log.info(f"Accepted from {peer_addr}")

        start_join_threads(peer_sock)


def udp_client(addr):
    sock = udp.dial(addr)
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
        default=tcp_client,
        const=tcp_server,
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

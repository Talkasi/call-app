import argparse
import sound as snd
import tcp
import udp
import logger
import pygame.image
import camera
from threading import Thread

buffer_size = None

CHUNK_SIZE = 16 * 3


def get_and_send_data(sock):
    cam = camera.camera_init()

    try:
        while True:
            camera_image = cam.get_image()

            data = bytes(list(pygame.image.tostring(camera_image, 'RGB')))

            sent_size = 0
            while sent_size < len(data):
                sent_size += sock.send(data[sent_size:sent_size + CHUNK_SIZE])
                print("Sent", data[sent_size:sent_size + CHUNK_SIZE], len(data[sent_size:sent_size + CHUNK_SIZE]))

            print("Send")
            logger.root_logger.debug(f"Got and sent {len(data)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_and_play_data(sock, resolution=(1280, 720)):
    window_display = pygame.display.set_mode(resolution)
    try:
        while True:
            size_received = 0
            data = b""
            while size_received < resolution[0] * resolution[1] * 3:  # Size of an image
                print("Received 1", sock.recv(CHUNK_SIZE))
                data += sock.recv(CHUNK_SIZE)
                print("Received 2", data)
                size_received += CHUNK_SIZE

            print("Receive")
            camera_image = pygame.image.fromstring(str(data), resolution, 'RGB')

            logger.root_logger.debug(f"Received and played {len(data)} bytes")

            if camera.camera_print_image(camera_image, window_display) == 0:
                pass
                # return
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


def start_join_threads(sock_tcp, sock_udp):
    read_send_thread = Thread(target=read_send, args=(sock_tcp,))
    receive_play_thread = Thread(target=receive_play, args=(sock_tcp,))

    receive_and_play_thread = Thread(target=receive_and_play_data, args=(sock_udp,))
    get_and_send_thread = Thread(target=get_and_send_data, args=(sock_udp,))

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


def server(addr):
    sock_tcp = tcp.listen(addr)
    sock_udp = udp.listen(addr)

    while True:
        peer_sock_tcp, (peer_host_tcp, peer_port_tcp) = sock_tcp.accept()
        peer_addr_tcp = tcp.get_addr(peer_host_tcp, peer_port_tcp)
        tcp.log.info(f"Accepted from {peer_addr_tcp}")

        start_join_threads(peer_sock_tcp, sock_udp)


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

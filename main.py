import argparse
import logger
import sound as snd
import pygame.image
import camera
import tcp
from threading import Thread

buffer_size = None
CHUNK_SIZE = 51200


def get_and_send_data(sock):
    cam = camera.camera_init()

    try:
        while True:
            camera_image = cam.get_image()
            data = pygame.image.tostring(camera_image, 'RGB')

            sent_size = 0
            while sent_size < len(data):
                sent_size += sock.send(data[sent_size:sent_size + CHUNK_SIZE])

            logger.root_logger.debug(f"Camera. Got and sent {len(data)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_and_play_data(sock, resolution=(1280, 720)):
    window_display = pygame.display.set_mode(resolution)

    try:
        while True:
            data = b''

            while len(data) < resolution[0] * resolution[1] * 3:  # Size of an image
                data += sock.recv(CHUNK_SIZE)

            camera_image = pygame.image.fromstring(data, resolution, 'RGB')
            if camera.camera_print_image(camera_image, window_display) == 0:
                pass
                # return

            logger.root_logger.debug(f"Camera. Received and played {len(data)} bytes")
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


def start_join_threads(sock_tcp_sound, sock_tcp_camera):
    read_send_thread = Thread(target=read_send, args=(sock_tcp_sound, ))
    receive_play_thread = Thread(target=receive_play, args=(sock_tcp_sound, ))
    receive_and_play_thread = Thread(target=receive_and_play_data, args=(sock_tcp_camera, ))
    get_and_send_thread = Thread(target=get_and_send_data, args=(sock_tcp_camera,))

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
    while True:
        sock_tcp_sound = tcp.listen(addr, 1234)

        peer_sock_tcp_sound, (peer_host_tcp_sound, peer_port_tcp_sound) = sock_tcp_sound.accept()
        peer_addr_tcp_sound = tcp.get_addr(peer_host_tcp_sound, peer_port_tcp_sound)
        tcp.log.info(f"Accepted from {peer_addr_tcp_sound}")

        sock_tcp_camera = tcp.listen(addr, 4321)

        peer_sock_tcp_camera, (peer_host_tcp_camera, peer_port_tcp_camera) = sock_tcp_camera.accept()
        peer_addr_tcp_camera = tcp.get_addr(peer_host_tcp_camera, peer_port_tcp_camera)
        tcp.log.info(f"Accepted from {peer_addr_tcp_camera}")

        start_join_threads(peer_sock_tcp_sound, peer_sock_tcp_camera)


def client(addr):
    sock_tcp_sound = tcp.dial(addr, 1234)
    sock_tcp_camera = tcp.dial(addr, 4321)

    start_join_threads(sock_tcp_sound, sock_tcp_camera)


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
    buffer_size = snd.instream.blocksize * 2 * 4  # NOTE: 4 kiB

    # NOTE: calling server or client function depending on provided arguments.
    try:
        args.handler(args.addr)
    except (ConnectionRefusedError, OSError) as e:
        logger.root_logger.fatal(e)


if __name__ == "__main__":
    main()

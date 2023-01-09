import argparse
import time
import logger
import sound as snd
import pygame.image
import camera
import tcp
import udp
import struct
from threading import Thread

buffer_size = None
CHUNK_SIZE = 1200


def get_and_send_data(sock):
    sock.settimeout(100)
    cam = camera.camera_init()

    try:
        while True:
            camera_image = cam.get_image()
            data = pygame.image.tostring(camera_image, 'RGB')

            sock.send(b'START')
            # print("SENDER: sent START")

            pack = b''
            while pack != b'STARTED':
                start_time = time.time()
                while time.time() - start_time < 100:
                    try:
                        pack = sock.recv(len(b'STARTED'))
                    except:
                        pack = b''

                    if pack == b'STARTED':
                        break
                    # print("SENDER: received wrong:", pack)
                else:
                    # print("SENDER: time out: sent START")
                    sock.send(b'START')
                    # print("SENDER: sent START")

            # print("SENDER: received STARTED")

            for i in range(640 * 480 * 3 // CHUNK_SIZE):
                sock.send(b''.join([struct.pack("i", i), data[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]]))

                pack = b''
                while pack != b'RECEIVED' + struct.pack("i", i):
                    start_time = time.time()
                    while time.time() - start_time < 100:
                        try:
                            pack = sock.recv(len(b'RECEIVED' + struct.pack("i", i)))
                        except:
                            pack = b''

                        if pack == b'RECEIVED' + struct.pack("i", i):
                            break
                        # print("SENDER: received wrong:", pack)
                    else:
                        # print("SENDER: time out: send pack")
                        sock.send(b''.join([struct.pack("i", i), data[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]]))
                        # print("SENDER: sent pack")

            #     print("SENDER: received", struct.unpack("8si", pack))
            #
            # print("SENDER: end of the `for` loop")

            logger.root_logger.debug(f"Camera. Got and sent {len(data)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_and_play_data(sock, pack=b'', resolution=(640, 480)):
    sock.settimeout(100)
    window_display = pygame.display.set_mode(resolution)

    try:
        while True:
            image = b''

            while pack != b'START':
                try:
                    pack = sock.recv(len(b'START'))
                except:
                    pack = b''

            # print("RECEIVER: received START")

            sock.send(b'STARTED')
            # print("RECEIVER: sent STARTED")

            prev_message = b'STARTED'

            for i in range(640 * 480 * 3 // CHUNK_SIZE):
                pack = b''
                while len(pack) != CHUNK_SIZE + 4 or struct.unpack("i", pack[:4])[0] != i:
                    start_time = time.time()
                    while time.time() - start_time < 100:
                        try:
                            pack = sock.recv(CHUNK_SIZE + 4)
                        except:
                            pack = b''

                        if len(pack) == CHUNK_SIZE + 4 and struct.unpack("i", pack[:4])[0] == i:
                            break
                        # print("RECEIVER: received wrong:", pack, time.time() - start_time)
                    else:
                        # print("RECEIVER: time out: send previous message")
                        sock.send(prev_message)
                        # print("RECEIVER: sent previous message")

                # print("Pack #{:g} arrived!".format(i))
                image += pack[4:]
                sock.send(b'RECEIVED' + struct.pack("i", i))
                prev_message = b'RECEIVED' + struct.pack("i", i)

            # print("RECEIVER: end of the `for` loop")

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


def start_join_threads(sock_tcp, sock_udp_send, sock_udp_receive, pack=b''):
    read_send_thread = Thread(target=read_send, args=(sock_tcp,))
    receive_play_thread = Thread(target=receive_play, args=(sock_tcp,))
    get_and_send_thread = Thread(target=get_and_send_data, args=(sock_udp_send,))
    receive_and_play_thread = Thread(target=receive_and_play_data, args=(sock_udp_receive, pack, ))

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
    '''
    ┌────────┬───────────┬──────────────┐
    │        │ Send port │ Receive port │
    ├────────┼───────────┼──────────────┤
    │ Server │    4321   │      1111    │
    └────────┴───────────┴──────────────┘
    '''
    sock_tcp = tcp.listen(addr)

    host = addr.split(':')[0]
    sock_udp_send = udp.listen(host, 4321)
    sock_udp_receive = udp.listen(host, 1111)

    while True:
        peer_sock_tcp, (peer_host_tcp, peer_port_tcp) = sock_tcp.accept()
        peer_addr_tcp = tcp.get_addr(peer_host_tcp, peer_port_tcp)
        tcp.log.info(f"Accepted from {peer_addr_tcp}")

        data_received, address = sock_udp_receive.recvfrom(3)
        sock_udp_receive.connect(address)
        sock_udp_receive.send(b'HI!')
        udp.log.info(f"Connected to {address[0] + ':' + str(address[1])}")

        data_received, address = sock_udp_send.recvfrom(3)
        sock_udp_send.connect(address)
        sock_udp_send.send(b'HI!')
        udp.log.info(f"Connected to {address[0] + ':' + str(address[1])}")

        start_join_threads(peer_sock_tcp, sock_udp_send, sock_udp_receive)


def client(addr):
    '''
    ┌────────┬───────────┬──────────────┐
    │        │ Send port │ Receive port │
    ├────────┼───────────┼──────────────┤
    │ Client │    1111   │      4321    │
    └────────┴───────────┴──────────────┘
    '''
    sock_tcp = tcp.dial(addr)

    host = addr.split(':')[0]

    # Connecting servers receiver
    sock_udp_send = udp.dial(host, 1111)
    sock_udp_send.settimeout(100)
    sock_udp_send.send(b'Hi!')

    pack = b''
    while pack != b'HI!':
        start_time = time.time()
        while time.time() - start_time < 100:
            pack = sock_udp_send.recv(3)
            if pack == b'HI!':
                break
        else:
            sock_udp_send.send(b'Hi!')

    # Connecting servers sender
    sock_udp_receive = udp.dial(host, 4321)
    sock_udp_receive.settimeout(100)
    sock_udp_receive.send(b'Hi!')

    pack = b''
    while pack != b'HI!':
        start_time = time.time()
        while time.time() - start_time < 100:
            pack = sock_udp_receive.recv(3)
            if pack == b'HI!':
                break
        else:
            sock_udp_receive.send(b'Hi!')

    start_join_threads(sock_tcp, sock_udp_send, sock_udp_receive)


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

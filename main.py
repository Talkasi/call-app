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
import queue

buffer_size = None
CHUNK_SIZE = 1500
q = queue.Queue(0)

def get_and_send_data(sock):
    sock.settimeout(100)
    cam = camera.camera_init()

    current_image_number = 0
    try:
        while True:
            camera_image = cam.get_image().convert_alpha()
            pygame.image.save(camera_image, "video.jpeg")
            # THIS IS SHIT
            file2 = open("video.jpeg", "rb")
            image = file2.read()
            file2.close()

            print(len(image))

            if current_image_number == 2 ** 32 - 1:
                current_image_number = 0

            for i in range(len(image) // CHUNK_SIZE + (len(image) / CHUNK_SIZE != 0)):
                sock.send(b''.join([struct.pack('i', len(image)), struct.pack('i', current_image_number),
                                    struct.pack('i', i), image[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]]))

            current_image_number += 1
            logger.root_logger.debug(f"Camera. Got and sent {len(image)} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def receive_data(sock, pack=b'', resolution=(640, 480)):
    sock.settimeout(100)

    current_image_number = 0
    queue = b''
    try:
        while True:
            if len(queue) != 0:
                data = [queue]
            else:
                data = []

            while True:
                try:
                    pack = sock.recv(CHUNK_SIZE + 12)
                    while struct.unpack('i', pack[4:8])[0] < current_image_number:
                        pack = sock.recv(CHUNK_SIZE + 12)
                        print("WRONG_PACK", struct.unpack('i', pack[4:8])[0], struct.unpack('i', pack[8:12])[0])
                        pass
                    # print("PACK", "IMAGE", struct.unpack('i', pack[:4])[0], "NUMBER", struct.unpack('i', pack[4:8])[0],
                    #       "LEN", 1 if len(pack) == CHUNK_SIZE + 8 else 0, len(data))
                    if struct.unpack('i', pack[4:8])[0] == current_image_number:
                        data += [pack]
                    if struct.unpack('i', pack[4:8])[0] > current_image_number:
                        # print("NEXT_IMAGE", struct.unpack('i', pack[:4])[0], struct.unpack('i', pack[4:8])[0])
                        queue = pack
                        break
                except TimeoutError:
                    pass

            print(len(data))
            q.put(data)
            current_image_number += 1

            logger.root_logger.debug(f"Camera. Received {len(data) * CHUNK_SIZE} bytes")
    except (BrokenPipeError, ConnectionResetError) as e:
        logger.root_logger.warning(e)


def play_data(resolution=(640, 480)):
    window_display = pygame.display.set_mode(resolution)
    while True:
        data = q.get()

        data = list(set(data))
        data.sort(key=lambda data_item: struct.unpack('i', data_item[8:12])[0])

        image = b''
        index_should_be = 0
        for i in range(len(data)):
            data_index = struct.unpack('i', data[i][8:12])[0]
            if data_index - index_should_be > 0:
                image += b'\x00' * (data_index - index_should_be) * CHUNK_SIZE
                index_should_be += data_index - index_should_be
            image += data[i][12:]
            index_should_be += 1

        image += b'\x00' * (struct.unpack('i', data[0][:4])[0] - len(image))
        # THIS IS SHIT
        file1 = open("video_receive.jpeg", "wb")
        file1.write(image)
        file1.close()

        camera_image = pygame.image.load("video_receive.jpeg")

        # try:
        #     camera_image = pygame.image.fromstring(image, resolution, 'RGB')
        # except:
        #     print("WRONG IMAGE LENGTH", len(image))
        #     exit()
        if camera.camera_print_image(camera_image, window_display) == 0:
            return
        logger.root_logger.debug(f"Camera. Played {len(image)} bytes")


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
    receive_and_play_thread = Thread(target=receive_data, args=(sock_udp_receive, pack,))
    play_thread = Thread(target=play_data, args=())

    read_send_thread.start()
    receive_play_thread.start()
    get_and_send_thread.start()
    receive_and_play_thread.start()
    play_thread.start()

    read_send_thread.join()
    receive_play_thread.join()
    get_and_send_thread.join()
    receive_and_play_thread.join()
    play_thread.join()

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

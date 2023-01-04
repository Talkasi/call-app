import socket
import struct
import threading

import pygame.image
import camera
import gzip

UDP_IP = "127.0.0.1"
UDP_PORT = 8080
MAX_PACK = 65507


def get_and_send_data(sock):
    sock.send(bytes(1))
    cam = camera.camera_init()

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


def receive_and_play_data(sock, resolution=(1280, 720)):
    sock.recv(1)
    window_display = pygame.display.set_mode(resolution)

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


# NOTE: Test part, will be removed
if a := int(input("b: ")):
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect((UDP_IP, UDP_PORT))
else:
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Bind server
    sock.bind((UDP_IP, UDP_PORT))

s = threading.Thread(target=receive_and_play_data, args=(sock, ))
d = threading.Thread(target=get_and_send_data, args=(sock, ))

s.start()
d.start()

s.join()
d.join()

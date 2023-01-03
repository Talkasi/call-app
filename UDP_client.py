import socket

import pygame.image
import camera
import gzip

UDP_IP = "192.168.43.71"
UDP_PORT = 8080

# Create a UDP socket
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.connect((UDP_IP, UDP_PORT))

cam = camera.camera_init()

while True:
    camera_image = cam.get_image()

    data = pygame.image.tostring(camera_image, 'RGB')
    print(len(data))

    data = gzip.compress(bytes(list(data)))
    print(len(data))

    # NOTE: Here size problem occurs
    client.send(data)

    get_data = client.recv(2764800)

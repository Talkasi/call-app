import socket
import pygame.image
import zlib
import camera

UDP_IP = "192.168.43.71"
UDP_PORT = 8080

# Create a UDP socket
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# Bind server
server.bind((UDP_IP, UDP_PORT))

# NOTE: This part wasn't implemented as it should be.
window_display = pygame.display.set_mode((1280, 720))
while True:
    data, addr = server.recvfrom(2764800)
    data = zlib.decompress(data).decode("ascii")

    camera_image = pygame.image.fromstring(data, (1280, 720), 'RGB')

    if camera.camera_print_image(camera_image, window_display) == 0:
        break

    server.sendto(data, addr)

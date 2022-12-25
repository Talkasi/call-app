import pygame.camera
import pygame.event as pg_event

resolution = (1280, 720)
camera_path = "/dev/video0"


def camera(camera_path):
    pygame.init()
    pygame.camera.init()

    cam = pygame.camera.Camera(camera_path, resolution)
    cam.start()
    window = pygame.display.set_mode(resolution)
    while True:
        image = cam.get_image()

        pygame.display.set_caption('video')

        window.blit(image, (0, 0))
        pygame.display.flip()

        for event_item in pg_event.get():
            if event_item.type == pygame.QUIT:
                pygame.quit()
                return 1

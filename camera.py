import pygame.camera
import pygame.event as pg_event


def camera(path="/dev/video0", resolution=(1280, 720), window_name="call-app"):
    pygame.init()
    pygame.camera.init()

    cam = pygame.camera.Camera(path, resolution)
    cam.start()
    window = pygame.display.set_mode(resolution)
    while True:
        image = cam.get_image()

        pygame.display.set_caption(window_name)

        window.blit(image, (0, 0))
        pygame.display.flip()

        for event_item in pg_event.get():
            if event_item.type == pygame.QUIT:
                pygame.quit()
                return

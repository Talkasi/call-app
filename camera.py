import pygame.camera
import pygame.event as pg_event


def camera_init(path="/dev/video0", resolution=(640, 480)):
    pygame.init()
    pygame.camera.init()

    cam = pygame.camera.Camera(path, resolution)
    cam.start()

    return cam


def camera_print_image(image, window_display, window_name="call-app"):
    pygame.display.set_caption(window_name)

    window_display.blit(image, (0, 0))
    pygame.display.flip()

    for event_item in pg_event.get():
        if event_item.type == pygame.QUIT:
            pygame.quit()
            return 0

    return 1

# Working stuff

# window_display = pygame.display.set_mode((1280, 720))
# camera = camera_init()
# while True:
#     camera_image = camera.get_image()
#     if camera_print_image(camera_image, window_display) == 0:
#         break

import cv2 as cv


def camera():
    cap = cv.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        cv.imshow('Video', frame)

        if cv.waitKey(1) == 27:
            break

    cap.release()
    cv.destroyAllWindows()


camera()

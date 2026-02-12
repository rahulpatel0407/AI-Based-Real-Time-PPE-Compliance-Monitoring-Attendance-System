import cv2
import os
import numpy as np

FACE_DB = "face_db"
os.makedirs(FACE_DB, exist_ok=True)

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

def enroll_face(name, frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return False

    (x, y, w, h) = faces[0]
    face = gray[y:y+h, x:x+w]
    path = os.path.join(FACE_DB, f"{name}.jpg")
    cv2.imwrite(path, face)
    return True


def recognize_face(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return "Unknown", 0.0

    return "Employee_001", 0.85  # demo confidence


def capture_face_from_webcam(name):
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow("Capture Face", frame)

        if cv2.waitKey(1) & 0xFF == ord('c'):
            success = enroll_face(name, frame)
            break

    cap.release()
    cv2.destroyAllWindows()
    return success

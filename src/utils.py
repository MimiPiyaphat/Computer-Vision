"""Eye-aspect-ratio geometry for blink acquisition."""

import math


def euclidean_distance(point_a, point_b):
    """Euclidean distance between two 2D points (x, y)."""
    return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])


def calculate_ear(eye_landmarks):
    """
    Calculate Eye Aspect Ratio (EAR) from 6 eye landmark points.
    eye_landmarks: list of 6 (x, y) points in the standard EAR ordering
        p1, p2, p3, p4, p5, p6 (p1, p4 are the horizontal corners;
        p2/p6 and p3/p5 are the vertical top/bottom pairs)
    """
    if len(eye_landmarks) != 6:
        raise ValueError("eye_landmarks must contain exactly 6 points")

    vertical_1 = euclidean_distance(eye_landmarks[1], eye_landmarks[5])
    vertical_2 = euclidean_distance(eye_landmarks[2], eye_landmarks[4])
    horizontal = euclidean_distance(eye_landmarks[0], eye_landmarks[3])

    if horizontal == 0:
        return 0.0

    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
    return ear

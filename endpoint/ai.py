import test


def classify_image_via_ai(image_path: str) -> int:
    """
    Run existing model and return label int.
    label: 0(can), 1(pet), 2(uncertain)
    """
    return int(test.predict_now(image_path))


import copy

import numpy as np
from PIL import Image


def create_images_list(data):
    assert len(data.shape) == 2, "data is error"

    save_data = copy.deepcopy(data)
    data = data[np.newaxis, :, :]
    save_data = save_data[np.newaxis, :, :]

    images = []
    for _img in save_data:
        images.append(_img.tolist())

    return images


def save_thumbnail(plot_file):
    try:
        img = Image.open(plot_file)
        img.thumbnail((100, 100))
        img.save(plot_file.replace(".png", "_thumbnail.png"), "PNG")
    except Exception as e:
        print(f"An error occurred while processing the image: {e}")
    finally:
        img.close()

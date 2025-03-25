import copy

import numpy as np
from PIL import Image

from studio.app.const import THUMBNAIL_HEIGHT


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
    with Image.open(plot_file) as img:
        # Calculate new dimensions
        w, h = img.size
        new_width = int(w * (THUMBNAIL_HEIGHT / h))
        # LANCZOS is high-quality downsampling filter
        # BILINEAR is faster
        thumb_img = img.resize((new_width, THUMBNAIL_HEIGHT), Image.Resampling.BILINEAR)
        thumb_img.save(plot_file.replace(".png", ".thumb.png"))

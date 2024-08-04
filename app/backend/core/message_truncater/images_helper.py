import base64
import math
import re
from io import BytesIO

from PIL import Image

"""
This function checks whether the base code encoded image is a valid base64 string
and returns the dimensions of the image.
"""


def get_image_dims(image_uri: str) -> tuple[int, int]:
    # From https://github.com/openai/openai-cookbook/pull/881/files
    if re.match(r"data:image\/\w+;base64", image_uri):
        image_uri = re.sub(r"data:image\/\w+;base64,", "", image_uri)
        image = Image.open(BytesIO(base64.b64decode(image_uri)))
        return image.size
    else:
        raise ValueError("Image must be a base64 string.")


"""
This function calculates the number of tokens required to encode an image.
"""


def count_tokens_for_image(image_uri: str, detail: str = "auto") -> int:
    # From https://github.com/openai/openai-cookbook/pull/881/files
    # Based on https://platform.openai.com/docs/guides/vision
    LOW_DETAIL_COST = 85
    HIGH_DETAIL_COST_PER_TILE = 170
    ADDITIONAL_COST = 85

    if detail == "auto":
        # assume high detail for now
        detail = "high"

    if detail == "low":
        # Low detail images have a fixed cost
        return LOW_DETAIL_COST
    elif detail == "high":
        # Calculate token cost for high detail images
        width, height = get_image_dims(image_uri)
        # Check if resizing is needed to fit within a 2048 x 2048 square
        if max(width, height) > 2048:
            # Resize dimensions to fit within a 2048 x 2048 square
            ratio = 2048 / max(width, height)
            width = int(width * ratio)
            height = int(height * ratio)
        # Further scale down to 768px on the shortest side
        if min(width, height) > 768:
            ratio = 768 / min(width, height)
            width = int(width * ratio)
            height = int(height * ratio)
        # Calculate the number of 512px squares
        num_squares = math.ceil(width / 512) * math.ceil(height / 512)
        # Calculate the total token cost
        total_cost = num_squares * HIGH_DETAIL_COST_PER_TILE + ADDITIONAL_COST
        return total_cost
    else:
        # Invalid detail_option
        raise ValueError("Invalid value for detail parameter. Use 'low' or 'high'.")
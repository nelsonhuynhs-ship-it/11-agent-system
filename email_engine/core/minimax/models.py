from enum import Enum

class TextModel(str, Enum):
    TEXT_01 = "MiniMax-Text-01"

class VLModel(str, Enum):
    VL_02 = "MiniMax-VL-02"

class ImageModel(str, Enum):
    IMAGE_01 = "MiniMax-Image-01"
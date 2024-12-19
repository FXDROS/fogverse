import base64
import cv2
import uuid
import os

from fogverse.utils.numpy import numpy_to_bytes, bytes_to_numpy

def get_cam_id():
    return f"cam_{os.getenv('CAM_ID', str(uuid.uuid4()))}"

def _encode(img, encoding, *args):
    _, encoded = cv2.imencode(f'.{encoding}', img, *args)
    return encoded

def compress_encoding(img, encoding, *args):
    encoded = _encode(img, encoding, *args)
    return numpy_to_bytes(encoded)

def _decode(img):
    return cv2.imdecode(img, cv2.IMREAD_COLOR)

def recover_encoding(img_bytes):
    img = bytes_to_numpy(img_bytes)
    return _decode(img)

def numpy_to_base64_url(img, encoding, *args):
    img = _encode(img, encoding, *args)
    b64 = base64.b64encode(img).decode()
    return f'data:image/{encoding};base64,{b64}'
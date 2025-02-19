import base64
import numpy as np
from io import BytesIO

from fogverse.utils.image_process import _encode

def bytes_to_numpy(bbytes):
    f = BytesIO(bbytes)
    return np.load(f, allow_pickle=True)

def numpy_to_base64_url(img, encoding, *args):
    img = _encode(img, encoding, *args)
    b64 = base64.b64encode(img).decode()
    return f'data:image/{encoding};base64,{b64}'

def numpy_to_bytes(arr):
    f = BytesIO()
    np.save(f,arr)
    return f.getvalue()
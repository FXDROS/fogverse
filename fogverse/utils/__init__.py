import inspect
import os
import sys

def get_size(obj, seen=None):
    """Recursively finds size of objects in bytes.\n
    Modified version of
    https://github.com/bosswissam/pysize/blob/master/pysize.py"""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)
    if hasattr(obj, '__dict__'):
        for cls in obj.__class__.__mro__:
            if '__dict__' in cls.__dict__:
                d = cls.__dict__['__dict__']
                if inspect.isgetsetdescriptor(d) \
                    or inspect.ismemberdescriptor(d):
                    size += get_size(obj.__dict__, seen)
                break
    if isinstance(obj, dict):
        size += sum((get_size(v, seen) for v in obj.values()))
        size += sum((get_size(k, seen) for k in obj.keys()))
    elif hasattr(obj, '__iter__') and not isinstance(obj,
                                                     (str, bytes, bytearray)):
        try:
            size += sum((get_size(i, seen) for i in obj))
        except TypeError:
            pass
    if hasattr(obj, '__slots__'): # can have __slots__ with __dict__
        size += sum(get_size(getattr(obj, s), seen)\
                    for s in obj.__slots__ if hasattr(obj, s))

    return size

def size_kb(obj, decimals=3):
    _size = get_size(obj)
    return round(_size/1e3, decimals)

def get_header(headers, key, default=None, decoder=None):
    if headers is None or key is None: return default
    for header in headers:
        if header[0] == key:
            val = header[1]
            if callable(decoder):
                return decoder(val)
            if isinstance(val, bytes):
                return val.decode()
            return val
    return default

class _Null:
    pass
_null = _Null()

# TODO: Look for a better way to implement .env
def get_config(config_name: str, cls: object=None, default=None):
    ret = os.getenv(config_name, _null)
    if not isinstance(ret, _Null): return ret
    if cls is None: return ret or default
    return getattr(cls, config_name.lower(), default)
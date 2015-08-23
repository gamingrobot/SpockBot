"""
ALL THE UTILS!
"""
import collections
import copy

from spock.vector import Vector3

try:
    string_types = unicode
except NameError:
    string_types = str


class Info(object):
    def set_dict(self, data):
        for key in data:
            if hasattr(self, key):
                setattr(self, key, data[key])

    def get_dict(self):
        return self.__dict__

    def __repr__(self):
        return repr(self.get_dict()).replace('dict', self.__class__.__name__)

    def __str__(self):
        return str(self.get_dict())


class Position(Vector3, Info):
    """
    Used for things that require encoding position for the protocol,
    but also require higher level vector functions.
    """

    def get_dict(self):
        d = self.__dict__.copy()
        del d['vector']
        d['x'], d['y'], d['z'] = self
        return d


class BoundingBox(object):
    def __init__(self, w, h, d=None, offset=(0, 0, 0)):
        self.x = offset[0]
        self.y = offset[1]
        self.z = offset[2]
        self.w = w  # x
        self.h = h  # y
        if d:
            self.d = d  # z
        else:
            self.d = w


class BufferUnderflowException(Exception):
    pass


class BoundBuffer(object):
    buff = b''
    cursor = 0

    def __init__(self, data=b""):
        self.write(data)

    def read(self, length):
        if length > len(self):
            raise BufferUnderflowException()

        out = self.buff[self.cursor:self.cursor+length]
        self.cursor += length
        return out

    def write(self, data):
        self.buff += data

    def flush(self):
        return self.read(len(self))

    def save(self):
        self.buff = self.buff[self.cursor:]
        self.cursor = 0

    def revert(self):
        self.cursor = 0

    def tell(self):
        return self.cursor

    def __len__(self):
        return len(self.buff) - self.cursor

    def __repr__(self):
        return "<BoundBuffer '%s'>" % repr(self.buff[self.cursor:])

    recv = read
    append = write


def create_namedtuple(mapping, replacements=None, name="Container"):
    if isinstance(mapping, collections.Mapping):
        if replacements:
            for old, new in replacements.items():
                if old in mapping:
                    mapping[new] = mapping.pop(old)
        for key, value in mapping.items():
            mapping[key] = create_namedtuple(value, replacements)
        try:
            return collections.namedtuple(name, mapping.keys())(**mapping)
        except ValueError:
            return mapping
    elif isinstance(mapping, list):
        for index, value in enumerate(mapping):
            mapping[index] = create_namedtuple(value, replacements)
        return tuple(mapping)
    return mapping


def pl_announce(*args):
    def inner(cl):
        cl.pl_announce = args
        return cl

    return inner


def pl_event(*args):
    def inner(cl):
        cl.pl_event = args
        return cl

    return inner


def get_settings(defaults, settings):
    return dict(copy.deepcopy(defaults), **settings)


def mapshort2id(data):
    return data >> 4, data & 0x0F


def byte_to_hex(byte_str):
    return ''.join(["%02X " % x for x in byte_str]).strip()

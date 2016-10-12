import base64
import bz2


def nrpe_encode(data):
    if not isinstance(data, bytes):
        data = bytes(data, "utf-8")
    return base64.b64encode(bz2.compress(data)).decode('ascii')

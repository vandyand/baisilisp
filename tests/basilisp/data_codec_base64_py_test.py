import io

from basilisp.data_codec_base64 import decoding_transfer, encoding_transfer
from basilisp.lang.primitive_array import byte_array


class PartialReader:
    """A stream whose reads are intentionally smaller than requested."""

    def __init__(self, data: bytes, chunk_size: int):
        self._stream = io.BytesIO(data)
        self._chunk_size = chunk_size

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = self._chunk_size
        return self._stream.read(min(size, self._chunk_size))


def test_transfers_fill_buffers_despite_partial_stream_reads():
    source = bytes(range(256)) * 17 + b"tail"
    encoded = io.BytesIO()
    encoding_transfer(PartialReader(source, 7), encoded, {"buffer-size": 12})

    decoded = io.BytesIO()
    decoding_transfer(
        PartialReader(encoded.getvalue(), 5), decoded, {"buffer-size": 16}
    )

    assert decoded.getvalue() == source


def test_codec_writes_raw_binary_bytes_to_a_clojure_compatible_byte_array():
    destination = byte_array(1)

    from basilisp.data_codec_base64 import decode_into

    assert decode_into(b"/w==", 0, 4, destination) == 1
    assert list(destination) == [-1]
    assert bytes(destination) == b"\xff"

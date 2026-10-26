"""Codec tests using frames captured from a real Aura Plus (FW 2.0.1)."""
import pytest

from custom_components.hkaura_plus import hk_bt_protocol as p


def test_query_frames():
    assert p.QUERY_POWER == b"\x0b\x01"
    assert p.QUERY_VOLUME_MUTE == b"\x02\x01"
    assert p.QUERY_SOURCE == b"\x0e\x01"
    assert p.QUERY_NAME == b"\x04\x01"
    assert p.QUERY_EQ_MODE == b"\x01\x01"


def test_wake_toggle_bytes_match_apk():
    assert p.POWER_TOGGLE == b"\x0b\x03\x00\x20"


def test_set_source_frame():
    assert p.set_source(p.Source.BLUETOOTH) == b"\x0e\x03\x02"
    assert p.set_source(p.Source.AIRPLAY) == b"\x0e\x03\x01"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(b"\x0b\x02\x01", True), (b"\x0b\x02\x00", False)],
)
def test_decode_power(raw, expected):
    assert p.decode_power(raw) is expected


def test_decode_volume_mute():
    assert p.decode_volume_mute(bytes.fromhex("02020014")) == p.VolumeMute(
        muted=False, volume=20
    )


def test_decode_source():
    assert p.decode_source(bytes.fromhex("0e0202")) is p.Source.BLUETOOTH
    assert p.decode_source(bytes.fromhex("0e0204")) is p.Source.OPTICAL


def test_decode_name_is_length_prefixed():
    raw = bytes.fromhex("04020e") + b"HK Aura WF 04F"
    assert p.decode_name(raw) == "HK Aura WF 04F"
    assert p.decode_name(bytes.fromhex("040207") + b"HK Aura") == "HK Aura"


def test_decode_eq_mode():
    assert p.decode_eq_mode(bytes.fromhex("01020a")) == 10


@pytest.mark.parametrize(
    "decoder",
    [p.decode_power, p.decode_volume_mute, p.decode_source, p.decode_name, p.decode_eq_mode],
)
def test_decoders_reject_wrong_type_or_short(decoder):
    with pytest.raises(p.ProtocolError):
        decoder(b"")
    with pytest.raises(p.ProtocolError):
        decoder(b"\x7f\x02\x00\x00")  # wrong type
    with pytest.raises(p.ProtocolError):
        decoder(b"\x0b\x01\x00")  # op!=0x02 is not a reply (for matching types)


def test_matches_reply():
    assert p.is_reply(b"\x0b\x02\x01", p.TYPE_POWER)
    assert not p.is_reply(b"\x02\x02\x00\x14", p.TYPE_POWER)
    assert not p.is_reply(b"\x0b\x01", p.TYPE_POWER)

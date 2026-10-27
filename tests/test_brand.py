"""The integration ships its own brand image (HA 2026.3+ reads <integration>/brand/)."""
import struct
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "hkaura_plus"
BRAND = INTEGRATION / "brand"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", data[16:24])


def test_icon_is_a_256_square_png():
    assert png_size(BRAND / "icon.png") == (256, 256)


def test_integration_directory_exposes_brand_folder():
    """HA's Integration.has_branding is exactly: 'brand' in the top-level files."""
    assert "brand" in {p.name for p in INTEGRATION.iterdir()}


async def test_home_assistant_serves_our_icon_file(hass, hass_client):
    """Drive HA's real brands view with our integration directory.

    The pytest harness resolves custom_components to its own test package, so
    discovery is stubbed; everything after discovery is HA's own code.
    """
    from homeassistant.setup import async_setup_component

    stub = SimpleNamespace(has_branding=True, file_path=INTEGRATION)

    async def fake_custom_components(_hass):
        return {"hkaura_plus": stub}

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        fake_custom_components,
    ):
        assert await async_setup_component(hass, "brands", {})
        client = await hass_client()
        resp = await client.get("/api/brands/integration/hkaura_plus/icon.png")
        assert resp.status == HTTPStatus.OK
        assert resp.content_type == "image/png"
        assert (await resp.read()) == (BRAND / "icon.png").read_bytes()
        # logo.png has no file of its own and falls back to icon.png
        resp = await client.get("/api/brands/integration/hkaura_plus/logo.png")
        assert resp.status == HTTPStatus.OK
        assert (await resp.read()) == (BRAND / "icon.png").read_bytes()

"""
QR Code MCP Server
===================
An MCP server providing QR code generation, generation with logos, and decoding.

Tools:
  - generate_qr: Generate a QR code PNG from text/URL, returned as base64
  - generate_qr_with_logo: Generate a QR code with a centered logo image
  - decode_qr: Decode a QR code from a base64-encoded PNG image
"""

import anyio
import base64
import http.client
import ipaddress
import io
import json
import ssl
from urllib.parse import urlparse
from typing import Optional

from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

import qrcode
from PIL import Image

# ---------------------------------------------------------------------------
# Server metadata
# ---------------------------------------------------------------------------

server = Server("qr-code-mcp")

# ---------------------------------------------------------------------------
# Helper: download an image from a URL into a PIL Image
# ---------------------------------------------------------------------------

def _download_image(url: str) -> Image.Image:
    """Download an image from *url* and return it as a PIL ``Image``."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https logo URLs are supported.")
    if not parsed.hostname:
        raise ValueError("Logo URL must include a hostname.")

    default_port = 443 if parsed.scheme == "https" else 80
    port = parsed.port or default_port
    request_path = parsed.path or "/"
    if parsed.query:
        request_path = f"{request_path}?{parsed.query}"

    if parsed.scheme == "https":
        connection = http.client.HTTPSConnection(
            parsed.hostname,
            port=port,
            timeout=15,
            context=ssl.create_default_context(),
        )
    else:
        connection = http.client.HTTPConnection(parsed.hostname, port=port, timeout=15)

    try:
        connection.connect()
        peer_ip = ipaddress.ip_address(connection.sock.getpeername()[0])
        if (
            peer_ip.is_private
            or peer_ip.is_loopback
            or peer_ip.is_link_local
            or peer_ip.is_multicast
            or peer_ip.is_reserved
            or peer_ip.is_unspecified
        ):
            raise ValueError("Logo URL resolved to a restricted network address.")

        connection.request("GET", request_path, headers={"Host": parsed.hostname})
        response = connection.getresponse()
        if response.status >= 400:
            raise ValueError(f"Logo URL returned HTTP {response.status}.")
        data = response.read()
    finally:
        connection.close()
    return Image.open(io.BytesIO(data)).convert("RGBA")


# ---------------------------------------------------------------------------
# Helper: paste a centred logo onto a QR code image
# ---------------------------------------------------------------------------

def _overlay_logo(qr_img: Image.Image, logo: Image.Image, max_logo_fraction: float = 0.3) -> Image.Image:
    """
    Resize *logo* so it occupies at most ``max_logo_fraction`` of the QR
    code's shortest dimension, then paste it centred onto *qr_img*.
    """
    qr_size = qr_img.size[0]  # square
    logo_max = int(qr_size * max_logo_fraction)

    # Scale logo preserving aspect ratio
    logo.thumbnail((logo_max, logo_max), Image.LANCZOS)

    # Centre on QR canvas
    offset = ((qr_size - logo.size[0]) // 2, (qr_size - logo.size[1]) // 2)

    # Create a white backing so transparent logos don't blend with QR modules
    result = qr_img.copy().convert("RGBA")
    white_bg = Image.new("RGBA", logo.size, (255, 255, 255, 255))
    result.paste(white_bg, offset)
    result.paste(logo, offset, mask=logo)
    return result


# ---------------------------------------------------------------------------
# Helper: encode a PIL Image as a base64 data-URI (PNG)
# ---------------------------------------------------------------------------

def _pil_to_base64_png(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Helper: decode a base64 PNG into a PIL Image
# ---------------------------------------------------------------------------

def _base64_to_pil(data: str) -> Image.Image:
    raw = base64.b64decode(data)
    return Image.open(io.BytesIO(raw))


# ---------------------------------------------------------------------------
# Helper: attempted decode via pyzbar (optional)
# ---------------------------------------------------------------------------

def _decode_with_pyzbar(image: Image.Image) -> Optional[list[str]]:
    """Try to decode a QR code with pyzbar. Return ``None`` if unavailable."""
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
    except ImportError:
        return None

    results = pyzbar_decode(image.convert("L"))
    if results:
        decoded_values: list[str] = []
        for result in results:
            decoded_values.append(result.data.decode("utf-8"))
        return decoded_values
    return None


def _normalize_size(value: object, default: int = 400, min_size: int = 64, max_size: int = 2048) -> int:
    """Return a validated integer QR size."""
    if value is None:
        return default
    if not isinstance(value, int):
        raise ValueError("size must be an integer.")
    if not min_size <= value <= max_size:
        raise ValueError(f"size must be between {min_size} and {max_size}.")
    return value


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _generate_qr_core(data: str, size: int) -> Image.Image:
    """
    Common logic: create a QR code with the *qrcode* library and return a
    PIL ``Image`` (square, ``size`` × ``size`` pixels).
    """
    qr = qrcode.QRCode(
        version=None,  # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # ~30% recovery
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    return img.resize((size, size), Image.LANCZOS)


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Advertise the three tools offered by this server."""
    return [
        types.Tool(
            name="generate_qr",
            description="Generate a QR code PNG from text or a URL and return it as a base64-encoded string.",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "The text or URL to encode in the QR code.",
                    },
                    "size": {
                        "type": "integer",
                        "description": "Pixel size (width/height) of the output PNG. Default: 400",
                        "default": 400,
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format. Only 'png' is supported. Default: 'png'",
                        "default": "png",
                        "enum": ["png"],
                    },
                },
                "required": ["data"],
            },
        ),
        types.Tool(
            name="generate_qr_with_logo",
            description="Generate a QR code with a centred logo image. Returns a base64-encoded PNG.",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "The text or URL to encode in the QR code.",
                    },
                    "logo_url": {
                        "type": "string",
                        "description": "URL of the logo/image to centre on the QR code. If omitted, behaves like generate_qr.",
                        "default": "",
                    },
                    "size": {
                        "type": "integer",
                        "description": "Pixel size (width/height) of the output PNG. Default: 400",
                        "default": 400,
                    },
                },
                "required": ["data"],
            },
        ),
        types.Tool(
            name="decode_qr",
            description="Decode a QR code from a base64-encoded PNG image. Requires pyzbar to be installed for actual decoding; otherwise returns instructions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_base64": {
                        "type": "string",
                        "description": "Base64-encoded PNG image data containing a QR code.",
                    },
                },
                "required": ["image_base64"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Dispatch tool calls to the appropriate handler."""

    if name == "generate_qr":
        data = arguments["data"]
        try:
            size = _normalize_size(arguments.get("size"))
        except ValueError as exc:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": str(exc)}),
                )
            ]
        img = _generate_qr_core(data, size)
        b64 = _pil_to_base64_png(img)
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "format": "png",
                    "base64": b64,
                    "mime_type": "image/png",
                }),
            )
        ]

    elif name == "generate_qr_with_logo":
        data = arguments["data"]
        try:
            size = _normalize_size(arguments.get("size"))
        except ValueError as exc:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": str(exc)}),
                )
            ]
        logo_url = arguments.get("logo_url", "")

        # Generate base QR code with a bit more error correction room
        img = _generate_qr_core(data, size)

        if logo_url:
            try:
                logo = _download_image(logo_url)
                img = _overlay_logo(img, logo)
            except Exception as exc:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({
                            "error": f"Failed to download or overlay logo: {exc}",
                            "base64": _pil_to_base64_png(img),
                            "note": "Falling back to QR code without logo.",
                        }),
                    )
                ]

        b64 = _pil_to_base64_png(img)
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "format": "png",
                    "base64": b64,
                    "mime_type": "image/png",
                }),
            )
        ]

    elif name == "decode_qr":
        image_b64 = arguments["image_base64"]
        try:
            pil_img = _base64_to_pil(image_b64)
        except Exception as exc:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Failed to decode base64 image: {exc}"}),
                )
            ]

        try:
            decoded_values = _decode_with_pyzbar(pil_img)
        except UnicodeDecodeError:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Decoded QR payload is not valid UTF-8 text.",
                    }),
                )
            ]
        if decoded_values:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "data": decoded_values[0],
                        "data_all": decoded_values,
                    }),
                )
            ]

        # pyzbar not installed or no code found
        has_pyzbar = False
        try:
            import pyzbar  # noqa: F401
            has_pyzbar = True
        except ImportError:
            pass

        if has_pyzbar:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "No QR code could be detected in the provided image.",
                    }),
                )
            ]
        else:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "pyzbar is not installed. To enable QR decoding, run: pip install pyzbar",
                        "hint": "On Windows you may also need to install ZBar from https://zbar.sourceforge.net/",
                    }),
                )
            ]

    else:
        raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="qr-code-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    anyio.run(main)

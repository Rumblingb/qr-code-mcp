# QR Code MCP Server

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![MCP](https://img.shields.io/badge/MCP-1.0+-green.svg)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that lets you **generate, decorate, and decode QR codes** directly from any MCP client (Claude Desktop, Cursor, VS Code via Continue.dev, etc.).

---

## Features

| Tool                    | Description                                      |
| ----------------------- | ------------------------------------------------ |
| `generate_qr`           | Generate a QR code PNG from text or a URL        |
| `generate_qr_with_logo` | Generate a QR code with a centered logo image    |
| `decode_qr`             | Decode a QR code from a base64-encoded PNG       |

---

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Create the project directory
mkdir qr-code-mcp && cd qr-code-mcp

# Install dependencies
pip install -r requirements.txt
```

> **Note for Windows users**: `pyzbar` requires the [ZBar library](https://zbar.sourceforge.net/). Download the Windows build and ensure `zbar.dll` is on your `PATH`, or use the [Windows PyPI wheel](https://pypi.org/project/pyzbar/).

### Run the server

```bash
python server.py
```

The server starts in **stdio mode**, ready to connect to any MCP client.

---

## MCP Client Configuration

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "qr-code-mcp": {
      "command": "python",
      "args": ["/absolute/path/to/qr-code-mcp/server.py"]
    }
  }
}
```

### VS Code (Continue.dev)

Add to your `~/.continue/config.json`:

```json
{
  "experimental": {
    "mcpServers": [
      {
        "name": "qr-code-mcp",
        "transport": "stdio",
        "command": "python",
        "args": ["/absolute/path/to/qr-code-mcp/server.py"]
      }
    ]
  }
}
```

---

## Usage Examples

### 1. Generate a QR code

```python
# Input
data = "https://example.com"
size = 400

# Returns:
# {
#   "format": "png",
#   "base64": "iVBORw0KGgo...",
#   "mime_type": "image/png"
# }
```

### 2. Generate a QR code with a logo

```python
# Input
data = "https://example.com"
logo_url = "https://example.com/logo.png"
size = 400

# Returns the same format as `generate_qr` with the logo centered
# on the QR code. If the logo download fails, the QR code is
# returned without the logo and an error note is provided.
```

### 3. Decode a QR code

```python
# Input
image_base64 = "iVBORw0KGgo..."

# Returns:
# {
#   "data": "https://example.com",
#   "data_all": ["https://example.com"]
# }
```

---

## API Reference

### `generate_qr(data, size?, format?)`

| Parameter | Type    | Default | Description                           |
| --------- | ------- | ------- | ------------------------------------- |
| `data`    | string  | --      | Text or URL to encode (required)      |
| `size`    | integer | `400`   | Width/height of the output PNG (`64`-`2048`) |
| `format`  | string  | `"png"` | Output format (currently only `"png"`) |

### `generate_qr_with_logo(data, logo_url?, size?)`

| Parameter  | Type    | Default | Description                                |
| ---------- | ------- | ------- | ------------------------------------------ |
| `data`     | string  | --      | Text or URL to encode (required)           |
| `logo_url` | string  | `""`    | Publicly accessible `http`/`https` URL of the logo image (private/internal IPs are blocked) |
| `size`     | integer | `400`   | Width/height of the output PNG (`64`-`2048`) |

### `decode_qr(image_base64)`

| Parameter      | Type   | Default | Description                           |
| -------------- | ------ | ------- | ------------------------------------- |
| `image_base64` | string | --      | Base64-encoded PNG data (required)    |

---

## Smithery Deployment

This server is ready to deploy on [Smithery.ai](https://smithery.ai). The `smithery.yaml` configuration is included in this repository.

---

## Pricing

**$19/month** — includes:
- Priority support
- No rate limits
- Commercial license

[Subscribe now](https://buy.stripe.com/dRm6oJ4Hd2Jugek0wz1oI0m)

---

## License

MIT

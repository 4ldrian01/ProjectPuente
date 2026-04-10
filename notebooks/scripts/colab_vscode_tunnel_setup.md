# Project PUENTE - VS Code <-> Colab Tunnel Setup (Phase A)

This guide is the markdown companion for the runnable notebook:

- `notebooks/colab_vscode_tunnel_setup.ipynb`

Use that notebook inside Colab in this exact order.

## Cell 1 (Storage)

```python
from google.colab import drive
drive.mount('/content/drive')
```

## Cell 2 (Dependencies)

```bash
%%bash
set -euo pipefail
apt-get update -y
apt-get install -y curl tar

mkdir -p /content/vscode-cli
curl -L "https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64" -o /tmp/vscode_cli.tar.gz
tar -xzf /tmp/vscode_cli.tar.gz -C /content/vscode-cli
chmod +x /content/vscode-cli/code
```

## Cell 3 (Tunnel Execution)

```bash
%%bash
set -euo pipefail
/content/vscode-cli/code tunnel --accept-server-license-terms --name puente-colab-rde
```

Colab will print a one-time sign-in URL + auth code. Complete auth in browser.

## Optional Keep-Alive Snippet (Browser Console)

```javascript
(() => {
	const clickConnect = () => {
		const button =
			document.querySelector('colab-connect-button')?.shadowRoot?.querySelector('#connect') ||
			document.querySelector('colab-toolbar-button#connect') ||
			document.querySelector('paper-button#connect');

		if (button) {
			button.click();
			console.log('[puente-keepalive] connect clicked at', new Date().toISOString());
		} else {
			console.log('[puente-keepalive] connect button not found');
		}
	};

	clickConnect();
	window.puenteKeepAliveInterval = setInterval(clickConnect, 10 * 60 * 1000);
})();
```

## Local VS Code Connection Guide

1. Install extension `ms-vscode.remote-server` (Remote - Tunnels).
2. In VS Code, open Command Palette with `Ctrl+Shift+P`.
3. Run `Remote Tunnels: Connect to Tunnel`.
4. Sign in with the same account used in Colab tunnel auth.
5. Choose tunnel name `puente-colab-rde`.
6. Open remote folder `/content/drive/MyDrive/ProjectPuenteCloud`.
7. Confirm the Project PUENTE root appears with `backend/`, `frontend/`, `datasets/`, and `ml_models/`.

## Why Project Root Mapping Matters

Opening `/content/drive/MyDrive/ProjectPuenteCloud` keeps all training outputs, LoRA adapters,
and run metadata inside Drive-backed storage, which survives Colab session resets.

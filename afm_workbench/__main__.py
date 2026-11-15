"""Desktop, browser-development, and MCP entry points."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys
import threading


def default_data_dir() -> Path:
    configured = os.environ.get('AFM_WORKBENCH_DATA')
    if configured:
        return Path(configured).expanduser()
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'AFM Workbench'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'AFM Workbench'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'afm-workbench'


class DesktopBridge:
    """Native file pickers and drops; scientific calls use the shared service."""
    def __init__(self):
        self._window = None

    def choose_folder(self):
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return str(result[0]) if result else None

    def _bind_folder_drop(self):
        # Register through pywebview's DOM API: this enables native full paths
        # on Cocoa and WebView2. Browser File objects alone do not expose them.
        from webview.dom import DOMEventHandler
        self._window.dom.document.events.drop += DOMEventHandler(
            self._on_folder_drop, prevent_default=True)
        self._window.evaluate_js('window.afmFolderDropReady = true;')

    def _on_folder_drop(self, event):
        files = event.get('dataTransfer', {}).get('files', [])
        if not files:
            return  # Text, links and internal drags are not folder imports.
        result = {}
        if len(files) != 1:
            result['error'] = 'Drop one session folder at a time.'
        else:
            path = files[0].get('pywebviewFullPath')
            if not isinstance(path, str) or not path:
                result['error'] = 'Could not read the dropped folder. Use Import folder to choose it.'
            elif not Path(path).is_dir():
                result['error'] = 'Drop a folder containing your AFM images, rather than an individual file.'
            else:
                result['path'] = path
        # JSON encoding keeps filenames (including quotes) out of executable JS.
        self._window.evaluate_js(f'window.afmImportDrop({json.dumps(result)});')

    def save_export(self, filename, content, is_base64=False):
        import webview
        try:
            # A proposed filename cannot select a directory; the user chooses it.
            name = Path(str(filename).replace('\\', '/')).name
            result = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=name)
            if not result:
                return {'cancelled': True}
            path = Path(result[0] if isinstance(result, (list, tuple)) else result)
            data = base64.b64decode(content, validate=True) if is_base64 else str(content).encode('utf-8')
            path.write_bytes(data)
            return {'path': str(path)}
        except Exception as exc:
            return {'error': str(exc)}


def main(argv=None):
    parser = argparse.ArgumentParser(description='AFM Workbench — browse a folder as one AFM session.')
    parser.add_argument('--data-dir', type=Path, default=default_data_dir(), help='Local catalog and managed source directory')
    parser.add_argument('--import', dest='import_path', type=Path, help='Import all supported images from this session folder')
    parser.add_argument('--demo', action='store_true', help='Create a clearly labeled synthetic example session')
    parser.add_argument('--browser', action='store_true', help='Run a loopback server instead of a desktop window')
    parser.add_argument('--port', type=int, default=0, help='Loopback port (default: random available port)')
    parser.add_argument('--mcp', action='store_true', help='Run the shared service as an MCP stdio server')
    parser.add_argument('--debug', action='store_true', help='Open desktop developer tools')
    parser.add_argument('--ready-file', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    from .service import Workbench
    workbench = Workbench(args.data_dir.expanduser().resolve())
    if args.import_path:
        workbench.dispatch('import_folder', {'path': str(args.import_path.expanduser().resolve())})
    if args.demo:
        workbench.dispatch('demo', {})
    if args.mcp:
        from .mcp import serve
        serve(workbench)
        return
    from .server import create_server
    server = create_server(workbench, port=args.port)
    if args.browser:
        # Windowed Windows executables have no stdout, even with redirected pipes.
        if args.ready_file:
            args.ready_file.write_text(server.url, encoding='utf-8')
        print(f'AFM Workbench: {server.url}', flush=True)
        print(f'Local workspace: {args.data_dir.resolve()}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return
    try:
        import webview
    except ImportError:
        server.server_close()
        parser.exit(1, 'Desktop runtime is missing. Install with: python -m pip install ".[desktop]"\nOr run with --browser.\n')
    bridge = DesktopBridge()
    thread = threading.Thread(target=server.serve_forever, name='afm-service', daemon=True)
    thread.start()
    webview.settings['ALLOW_FILE_URLS'] = False
    window = webview.create_window('AFM Workbench', server.url, js_api=bridge,
                                   width=1440, height=960, min_size=(900, 650),
                                   background_color='#e8eaec', text_select=True)
    bridge._window = window
    window.events.loaded += bridge._bind_folder_drop
    try:
        webview.start(debug=args.debug, private_mode=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    main()

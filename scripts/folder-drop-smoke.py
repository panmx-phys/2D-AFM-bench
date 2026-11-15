"""Exercise the native pywebview drop bridge against a running packaged server.

Usage: .venv/bin/python scripts/folder-drop-smoke.py http://127.0.0.1:8775
Use a disposable server catalog. Synthetic drop events and the native path cache
stand in for the OS drag gesture; this does not verify Finder/File Explorer input.
"""
from pathlib import Path
import json
import sys
import tempfile
import time

import numpy as np
import webview
from webview.dom import _dnd_state

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from afm_workbench.__main__ import DesktopBridge
from test_importers import park_fixture


def wait_for(window, expression):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if window.evaluate_js(expression):
            return
        time.sleep(0.1)
    raise AssertionError(f'Timed out: {expression}')


def drop(window, paths):
    # pywebview normally fills this cache from Cocoa/WebView2 drag payloads.
    _dnd_state['paths'].extend((p.name, str(p)) for p in paths)
    names = json.dumps([p.name for p in paths])
    window.evaluate_js(f'''(() => {{
      const transfer = new DataTransfer();
      for (const name of {names}) transfer.items.add(new File([''], name));
      document.dispatchEvent(new DragEvent('dragenter', {{bubbles:true, dataTransfer:transfer}}));
      if (document.getElementById('folder-drop').hidden) throw Error('Missing drop target');
      // WebView2 rejects synthetic Files at its OS-path extraction API. This
      // smoke already supplies that path cache above; simulate only that step,
      // keeping the actual DOM event, serialization and Python bridge intact.
      const nativeBridge = window.chrome?.webview;
      const original = nativeBridge?.postMessageWithAdditionalObjects;
      if(original) nativeBridge.postMessageWithAdditionalObjects = function(message, objects) {{
        if(message !== 'FilesDropped') return original.call(nativeBridge, message, objects);
      }};
      try {{
        document.dispatchEvent(new DragEvent('drop', {{bubbles:true, cancelable:true, dataTransfer:transfer}}));
      }} finally {{
        if(original) nativeBridge.postMessageWithAdditionalObjects = original;
      }}
    }})()''')


outcome = {}
with tempfile.TemporaryDirectory(prefix='afm-native-drop-') as root:
    folder = Path(root) / "Session 'quoted' μm"
    folder.mkdir()
    for n in range(1, 4):
        (folder / f'{n:03d}__Z Height_Forward.tiff').write_bytes(
            park_fixture(np.arange(48).reshape(6, 8)*n, gain=1, scale=2, offset=3, unit='nm'))
    bridge = DesktopBridge()
    window = webview.create_window('AFM folder drop verification', sys.argv[1], js_api=bridge)
    bridge._window = window
    window.events.loaded += bridge._bind_folder_drop

    def check():
        try:
            wait_for(window, 'window.afmFolderDropReady && !!document.querySelector(".session-heading")')
            window.evaluate_js('window.__dropErrors=[];window.addEventListener("error",e=>window.__dropErrors.push(e.message))')
            drop(window, [folder])
            wait_for(window, "state.importJob?.status==='completed'")
            job = window.evaluate_js('state.importJob')
            assert (job['added'], job['skipped'], job['errors']) == (3, 0, []), job
            assert window.evaluate_js('document.getElementById("folder-drop").hidden')
            first_id = job['session_id']
            window.evaluate_js('state.importJob=null')
            drop(window, [folder])
            wait_for(window, "state.importJob?.status==='completed'")
            job = window.evaluate_js('state.importJob')
            assert (job['added'], job['skipped'], job['session_id']) == (0, 3, first_id), job
            drop(window, [folder / '001__Z Height_Forward.tiff'])
            wait_for(window, 'document.getElementById("toast").textContent.includes("Drop a folder")')
            drop(window, [folder, folder])
            wait_for(window, 'document.getElementById("toast").textContent.includes("one session folder")')
            window.evaluate_js('openSession(state.importJob.session_id)')
            wait_for(window, 'document.querySelectorAll(".acquisition-card").length===3')
            outcome.update(passed=True, os_path_extraction='simulated, not a physical drop', checks=['Native DOM drop bridge', 'hover target',
                'quoted Unicode folder path', 'background import', 'repeat drop without duplicates',
                'individual file rejection', 'multiple folder rejection', 'contact sheet'])
        except Exception as exc:
            outcome.update(passed=False, error=str(exc))
            outcome['diagnostics'] = window.evaluate_js('({platform:pywebview.platform,errors:window.__dropErrors,toast:document.getElementById("toast").textContent,job:state.importJob})')
        finally:
            window.destroy()

    webview.start(check, private_mode=True)
print(json.dumps(outcome, indent=2))
sys.exit(0 if outcome.get('passed') else 1)

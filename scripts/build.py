"""Build an unsigned distribution for the host OS; ad-hoc sign local Mac output.

The generated bundle contains no workspace or experimental data. A distributable
Mac release still needs Developer ID signing and notarization by its publisher.
"""
from pathlib import Path
import os
import subprocess
import sys
from source_release import create_source_release

root = Path(__file__).resolve().parents[1]
os.environ.setdefault('PYTHONHASHSEED', '0')
os.environ.setdefault('SOURCE_DATE_EPOCH', subprocess.check_output(
    ['git', 'show', '-s', '--format=%ct', 'HEAD'], cwd=root, text=True).strip())
# Fail before producing a distributable binary if corresponding sources have
# not been collected for this build's dependency manifest.
create_source_release(root / 'dist' / 'AFM-Workbench-source.tar.gz')
subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', str(root / 'AFM-Workbench.spec')], cwd=root, check=True)
if sys.platform == 'darwin':
    app = root / 'dist' / 'AFM Workbench.app'
    # Finder/file-provider metadata on generated files can prevent codesigning.
    # Remove only resource metadata; never strip quarantine or security attributes.
    for attr in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
        subprocess.run(['xattr', '-dr', attr, str(app)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
    # A file provider can reattach Finder metadata to the bundle root while the
    # recursive cleanup visits its contents. Clear that root immediately before
    # signing, without touching quarantine or other security attributes.
    for attr in ('com.apple.ResourceFork', 'com.apple.FinderInfo'):
        subprocess.run(['xattr', '-d', attr, str(app)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app)], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
print(f'Built application in {root / "dist"}')

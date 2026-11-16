# Installing AFM Workbench

You don't need a GitHub account, Python or any other software.

## 1. Download

| Your computer | Download |
| --- | --- |
| Windows 10 or 11 | [AFM-Workbench-Windows.exe](https://github.com/panmx-phys/2D-AFM-bench/releases/latest/download/AFM-Workbench-Windows.exe) |
| Mac with an Apple chip (M1, M2, M3, M4 …), macOS 14 or newer | [AFM-Workbench-Mac.app.tar.gz](https://github.com/panmx-phys/2D-AFM-bench/releases/latest/download/AFM-Workbench-Mac.app.tar.gz) |

These links always download the newest version. The [release page](https://github.com/panmx-phys/2D-AFM-bench/releases/latest) lists what changed. You only need the one file for your computer; ignore the other files on that page.

Intel Macs are not supported. To check your Mac, open the Apple menu  → **About This Mac**. "Chip: Apple M…" works; "Processor: Intel" does not.

## 2. Open it for the first time

The app is experimental and not yet signed by Microsoft or Apple, so your computer warns you the first time. This is expected; you only need to do these steps once.

### Windows

1. If your browser warns that the file "isn't commonly downloaded", keep it. In Edge: **⋯ → Keep → Show more → Keep anyway**.
2. Move `AFM-Workbench-Windows.exe` somewhere permanent, such as Desktop or Documents, then double-click it. There is no installer. To add a desktop shortcut, right-click the file → **Show more options → Send to → Desktop (create shortcut)**.
3. If a blue **Windows protected your PC** box appears, click **More info**, then **Run anyway**.
4. The first start can take a moment while the app unpacks itself.

If Windows reports that **WebView2** is missing, install Microsoft's free [Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) (choose the *Evergreen Bootstrapper*) and try again. Windows 11 already includes it.

### Mac

1. If your browser has not already unpacked the download, double-click `AFM-Workbench-Mac.app.tar.gz` in **Downloads**. You now have **AFM Workbench.app**.
2. Drag **AFM Workbench.app** into **Applications**.
3. Double-click it. When macOS says it cannot verify the app, click **Done**. Don't move it to the Bin.
4. Open **System Settings → Privacy & Security**, scroll down to the message about "AFM Workbench", click **Open Anyway**, then confirm with your password or Touch ID.

On macOS 14 you can instead Control-click the app, choose **Open**, then **Open** again.

## 3. Use it

Drag a folder of AFM scans into the window, or click **Import folder**. One folder is one session; all channels and scan directions inside it stay together. The [README](../README.md) describes the views and analysis tools.

The app works offline and never changes your original files. It keeps its own copy in a workspace folder:

- **Windows:** `%LOCALAPPDATA%\AFM Workbench`. Paste this into the File Explorer address bar.
- **Mac:** `~/Library/Application Support/AFM Workbench`. In Finder, choose **Go → Go to Folder…** and paste it.

## Updating

Download again using the links above and replace the old app (Windows: overwrite the `.exe`; Mac: replace the app in Applications). Imported sessions live in the workspace folder, not inside the app, so they are kept.

## Problems

- **Nothing happens or the window closes immediately:** try once more. On Windows, also check that WebView2 is installed (see above).
- **Mac says the app "is damaged":** move it to Applications, then open **Terminal** and run
  `xattr -dr com.apple.quarantine "/Applications/AFM Workbench.app"`. This removes the download flag from this one app only. Then open the app again.
- **Anything else:** ask the lab member who maintains AFM Workbench, or [report an issue](https://github.com/panmx-phys/2D-AFM-bench/issues/new) (this needs a free GitHub account). Say which computer you used and what you saw.

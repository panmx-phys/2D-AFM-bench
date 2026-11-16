## Download

| Your computer | File to download | Size |
| --- | --- | --- |
| **Windows** 10 or 11 | [**AFM-Workbench-Windows.exe**](https://github.com/{repo}/releases/download/{tag}/AFM-Workbench-Windows.exe) | {windows_size} |
| **Mac** with an Apple chip (M1, M2, M3, M4 …), macOS 14 or newer | [**AFM-Workbench-Mac.app.tar.gz**](https://github.com/{repo}/releases/download/{tag}/AFM-Workbench-Mac.app.tar.gz) | {mac_size} |

You need only **one** file. Everything else on this page is for developers; you can ignore it.
Intel Macs are not supported. To check your Mac, open the Apple menu  → **About This Mac**: "Chip: Apple M…" works, "Processor: Intel" does not.

> [!NOTE]
> **Experimental version.** Microsoft and Apple have not yet signed these apps, so your computer shows a warning the first time you open one. The steps below show how to open it anyway. You only need to do this once.

### Windows: first start

1. Click the Windows download link above. If your browser warns that the file "isn't commonly downloaded", keep it. In Edge: **⋯ → Keep → Show more → Keep anyway**.
2. Move the file somewhere permanent, such as your Desktop or Documents folder, and double-click it. There is no installer.
3. If a blue **Windows protected your PC** box appears, click **More info**, then **Run anyway**.
4. The first start can take a moment while the app unpacks itself.

If Windows reports that WebView2 is missing, install Microsoft's free [Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) and try again. It is already part of Windows 11.

### Mac: first start

1. Click the Mac download link above. If your browser has not already unpacked it, double-click the downloaded file in **Downloads**. You now have **AFM Workbench.app**.
2. Drag **AFM Workbench.app** into your **Applications** folder.
3. Double-click it. When macOS says it cannot verify the app, click **Done**.
4. Open **System Settings → Privacy & Security**, scroll down, click **Open Anyway** next to "AFM Workbench", and confirm.

### Using it

Drag a folder of AFM scans into the window, or click **Import folder**. One folder is one session. The app works offline, keeps its own copy of your files and never changes the originals.

### Getting a newer version

The newest version is always at **<https://github.com/{repo}/releases/latest>**. Download it and replace the old app. Your imported sessions are stored separately and stay where they are.

More help, including where your data is stored: [installation guide](https://github.com/{repo}/blob/main/docs/install.md).

<details>
<summary>Technical details for developers: checks, provenance and checksums</summary>

{details}

### SHA-256 of the app downloads

```text
{checksums}
```

Verify with PowerShell `Get-FileHash -Algorithm SHA256 <file>` or macOS `shasum -a 256 <file>`.

</details>

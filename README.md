# AFM Workbench

A local desktop workbench for browsing AFM sessions and following interesting images into reproducible analysis. **One folder is one session.** Every channel and forward/backward image stays together.

- A compact contact sheet centered on one forward Z-height image per acquisition, with matching error and other signals beside it. All channels and directions remain available through the channel selector.
- A sample map at recorded positions and physical sizes, with focus, image and outline views. Overlap selection reaches every acquisition and its channels.
- Side-by-side comparison of up to four images, with an optional shared display range for matching units.
- Gwyddion C plane/polynomial leveling, eight row/column alignment methods, and zero references, saved when applied and undoable step by step.
- Full-resolution profiles with width averaging, selected-area statistics and two-region mean step-height measurements.
- Immutable managed originals, source checksums, saved recipes, session notes, CSV, PNG figures and JSON provenance exports.
- The same local Python service exposed through the GUI and a small MCP stdio adapter. No account, cloud or model required.

## Run

Python 3.10 or newer is required. Python 3.12 is the reference development environment.

```sh
python -m venv .venv
```

Activate on macOS:

```sh
source .venv/bin/activate
```

Activate on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Build the native scientific backend before installing. On macOS with Homebrew:

```sh
brew install glib fftw pkg-config
python scripts/build_gwyddion.py --download
```

See [native build instructions](native/README.md) for Linux, explicit dependency locations and the source bundle. Native execution has been tested on macOS arm64. Windows remains a platform target; its native backend build and packaging have not been validated. There is no silent Python fallback if the native library is missing.

Then install and open:

```sh
python -m pip install '.[desktop]'
python -m afm_workbench
```

On Windows the desktop renderer requires the Microsoft Edge WebView2 Runtime. On macOS it uses the system WebKit renderer. See [pywebview installation](https://pywebview.flowrl.com/guide/installation.html).

Drag a session folder from Finder or File Explorer anywhere into the desktop window, or click **Import folder** and choose it. Drop one folder at a time; the same background import shows progress and supports cancellation. Browser development mode uses **Import folder** and a local path because browsers do not expose dropped folders' full paths. Importing a folder copies its calibrated source files into the managed workspace. No source TIFF is modified. A repeated import of the same folder adds only new content. Unsupported files and import failures are reported; rendered TIFF previews are never treated as numerical height data.

To explore without experimental data:

```sh
python -m afm_workbench --demo
```

To use a particular local workspace and import a session:

```sh
python -m afm_workbench --data-dir ./my-workspace --import /path/to/session
```

Run the interface in a browser for development (no desktop dependencies needed):

```sh
python -m pip install .
python -m afm_workbench --browser --demo --port 8765
```

Open the loopback URL printed by the command. The browser mode's import dialog accepts a local folder path; the desktop version opens a native folder picker.

## Manage session folders

Open **Folders** in the sidebar, or **Manage folder** above a session. Rename sessions, edit notes, update imports, and reconnect a moved source folder. **Archive** hides a session without deleting images, source copies, recipes or measurements; restore it under **Folders → Archived**. These controls organize the catalog; they do not rename, move or delete your source directories.

**Update** checks the existing source folder. Imports run in the background with file progress, counts of added/unchanged/failed files, and error details. Keep browsing while they run. **Cancel import** stops after the current file; completed files remain saved. Retrying skips previously imported bytes. Changed files become additional image versions, preserving the earlier image and its analysis. One import runs at a time. Use **Open session** in the completion notice to view a new import.

If a folder is unavailable, use **Manage → Reconnect** and choose its new location. The session keeps its ID, notes and analysis; previous folder locations are recorded, and newly imported images record their source paths. Import progress is kept for the current application process; after a restart, update again to resume from the saved files.

## A PI's quick pass

1. Open a session and scan the contact sheet. Each acquisition starts with one forward Z-height image and signals from the same direction and recorded footprint. If forward height is absent, the fallback is labeled. Choose **All channels** or expand an acquisition's channel list to reach every image in the folder. **Leveled thumbnails** (on by default) applies display-only scan-line and plane leveling to unprocessed height thumbnails so features are visible at a glance; card statistics remain those of the stored data and are marked *unleveled*. Turn it off to see the stored data.
2. Choose **Sample map** to see acquisition locations. **Focus** shows the selected image with all footprints outlined. Click an overlapping area to choose from every scan covering that point, or select any acquisition in the list. **All images** brings the selected scan to the front; **Outlines** shows coverage alone. Only the selected scan is labeled on the map. Choose **Open channels** to open its channel and direction. Recorded positions stay fixed; images are not interpolated across gaps.
3. Star images worth returning to. Select two to four card checkboxes and choose **Compare images**.
4. Open an image. Switch between height and its signals in the header's channel menu, and between forward and backward with the header button or **B**. Arrow keys move through the same channel and direction across acquisitions in the height overview, or through all images in the other views. Press **S** to star.
5. Opening an unprocessed Z-height image automatically applies and saves scan-line alignment, three-point leveling on one inferred plane, and outline contrast. A message offers **Undo**; inspect the three numbered points and compare **Original** and **Result**. Every correction is saved to the image's recipe as soon as you apply it, and **⌘/Ctrl Z** or Record's undo removes the last one; the original file is never changed. Drag a **Contrast** rectangle (shortcut **C**) over a terrace or particle to set its display range immediately. **Prepare** opens with **Scan lines**: choose **Rows** or **Columns** (the file's axis is marked) and click a method to apply it. Each click replaces the previous scan-line correction rather than stacking; **Off** removes it, and **Terrace** restores Auto level's terrace-aware correction. A chosen method runs before Auto level's plane fit; if that fit then fails, Auto level is removed and the notice asks for three points (undo restores it). **Level surface** follows with **Auto level**, **3-point level** and the reference region; plane, polynomial, terrace, zero-reference and scan-axis controls sit under **More corrections**, and the mask below. ⌘/Ctrl Z steps back to the previous recipe. If automatic reference selection fails, the notice offers **Choose 3 leveling points**; click three clean, well-spaced points on the same plane. The **Auto level new height images when opened** preference at the bottom of Prepare can be turned off; with it on, browsing into an unprocessed height image saves that recipe. Images that already have a recipe are never automatically extended. Measure offers line profiles, two-region step heights and area roughness. Record holds correction history, undo and acquisition provenance. The export button remains above the image.
6. Use **Notes** for session notes and **Details** for source-folder and import metadata. Mark images reviewed and export calibrated data with its provenance manifest. “Reviewed” is a workflow label, not a scientific validation claim.

Use the **small arrow at the right of the image header** to hide the processing toolbar, inspector and on-image overlays (mask, contrast rectangle, profile/area/step guides and leveling points). Click it again to restore them. The image gains space; calibration, zoom and pan remain available. Hidden guides cannot be edited. Masks, selected regions, contrast limits and processing settings are retained, and the visibility preference is remembered locally. Choosing a drawing tool by shortcut or pressing **1–4** restores the controls. PNG figures omit the mask overlay while controls are hidden.

### Masks and color limits

Choose **Mask** or open **Prepare** to mark pixels. Click **Rectangle / Brush** and **Add / Erase** directly; the brush radius is in original image pixels. **Select by value** marks a calibrated value range on the saved result. Each edit is saved with its image and can be undone or redone; **Invert** and **Clear** are also reversible. **Done drawing** leaves the mask tool. The blue overlay can be hidden without changing the selection.

The mask menu controls whether corrections and measurements **exclude marked pixels**, **use only marked pixels**, or **ignore the mask**. An Area selection further restricts the reference or measurement region. Saved corrections and measurements retain their own mask snapshot, so later drawing does not alter an earlier result. Masks never replace image heights or modify the original file. Select **Result** before editing a mask.

In **View → Color & contrast**, enter calibrated **Min / Max** values and press **Enter** or **Set**, or drag either handle on the single range track below the histogram. Fields show compact numbers; focusing a field reveals the exact stored value. Setting one limit preserves the untouched limit's full precision. **Auto** trims 2% from each end; expand **Auto-range options** to tune that fraction. **Full** restores the finite minimum and maximum. **Auto contrast** is also available above the image from every tab. Manual limits remain fixed when comparing Original and Result, and settings persist separately for each image. Color changes affect only display and figures; numerical measurements and CSV heights are unchanged. PNG figures include the displayed limits and the mask overlay when it is visible.

Choose **Select region** in View, **Contrast** above the canvas, or press **C**, then drag a rectangle to apply its full-resolution limits immediately. Move a completed rectangle by dragging inside it; resize it by dragging an edge or corner handle. Its outline stays visible through corrections, undo, tools and inspector tabs while the image remains open. **Edit region** returns to Contrast; drag outside the current rectangle to replace it. **Use region** uses the contrast rectangle, or the separate measurement **Area** if no contrast rectangle is selected. A contrast rectangle never becomes a fit or measurement reference. **Clear** removes its outline while keeping the current display limits. Reopening an image retains saved limits but starts without a contrast outline. Clicks and flat drags do not replace a completed region; a new rectangle needs at least three screen pixels in each dimension.

Scroll or pinch over the canvas to zoom around the pointer. The visible **− / + / Fit** controls and **− / + / F** keys provide the same navigation. Magnification runs from 100% to 1600% relative to the fitted image, rather than source pixels. Hold **Space** and drag, or drag with the middle mouse button, to pan without changing the active tool; **H** selects Pan. Selections remain in source-image coordinates under zoom and pan. Navigation changes only the view.

Tabs preserve selections and their own scroll position; advanced sections retain their open state during the running session. Press **1–4** for the four inspector tabs, **C** for contrast, **V / H / P / A / M / T** for Inspect / Pan / Profile / Area / Mask / Step, **B** for the other scan direction, and **⌘/Ctrl Z** to undo the last correction. **Escape** first cancels an active drag, retaining the previous selection; otherwise it leaves the drawing tool, then returns to the session on another press. Losing pointer capture or switching away from the window also cancels an unfinished drag. Arrow keys inside fields and the tab strip adjust that control rather than changing the image. See the [interface references and community feedback](docs/interface-design.md) for the design rationale.

Side-by-side comparison starts with each image's saved limits and palette. **Shared display range** uses common limits and one palette for channels with the same unit. Comparison statistics follow each image's mask setting.

## Coordinates and scientific limits

The sample map is a metadata-positioned overview in the instrument's coordinate frame. It preserves overlapping scans and offers all channels at each location. It is **not** a drift-corrected, image-registered or blended topography. Scan footprints use recorded position, extent and angle; thumbnail pixels retain their explicitly recorded display orientation. Unknown position metadata is never invented.

Roughness is measured relative to the selected region's mean; background correction is explicit. Display contrast and color maps never modify numerical data. Measurements use the full-resolution data, while the large canvas can use a reduced display array. Profiles offer linear or nearest interpolation and averaging width. Step height is the signed difference between two region means. See the [Gwyddion comparison](docs/gwyddion-compatibility.md) for executed numerical checks and intentional differences. These measurements alone do not establish a physical mechanism or quantify instrument uncertainty.

See [supported formats and calibration](docs/formats.md), [scientific methods](docs/science.md), [architecture](docs/architecture.md), and [validation status](docs/validation.md).

## Local data

Set `--data-dir` or `AFM_WORKBENCH_DATA` to choose the workspace. Defaults are:

| System | Workspace |
| --- | --- |
| macOS | `~/Library/Application Support/AFM Workbench` |
| Windows | `%LOCALAPPDATA%/AFM Workbench` |
| Linux browser development | `$XDG_DATA_HOME/afm-workbench`, defaulting to `~/.local/share/afm-workbench` |

The catalog uses SQLite and references managed originals and numerical arrays. Close the app before copying the **entire workspace directory** for a consistent manual backup. Do not put a live catalog on a network filesystem or synchronize it between running copies. A shared database is future work.

Experimental files under `tests/data/local/` and workspaces under `.afm-workbench/` are ignored by version control and excluded from application bundles. Only generated synthetic data is included for examples and automated tests.

## Tests and packaging

Use the [test catalog and focused workflow](docs/testing.md). The catalog includes every Python test module, browser/native smoke script and the reference-fixture generator; the runner checks that new files are registered.

```sh
python scripts/test.py --plan                    # affected checks and selection reasons
python scripts/test.py                           # run those checks
python scripts/test.py --group display --plan    # inspect a specific feature group
python scripts/test.py --full --kind unit        # full Python regression when needed
python scripts/test.py --list                    # catalog and legacy notes
```

Normal runs select staged, unstaged and untracked changes relative to HEAD. Use `--base REVISION` for committed changes. `--kind unit` limits a run to Python tests and explicitly lists affected GUI checks as deferred. Each run saves logs, timing and a JSON report in `.test-artifacts/runs/`; past passes are not reused as current results. Six browser scripts still expect the removed preview workflow and are explicitly cataloged as legacy, with coverage gaps documented.

After completed changes, stage new source files and rebuild the desktop application, then run the relevant smoke checks against its executable. For example, on macOS:

```sh
python -m pip install '.[desktop,build]'
python scripts/build.py
python scripts/test.py --check runtime --bundle "dist/AFM Workbench.app/Contents/MacOS/AFM Workbench"
# For canvas changes, use --check canvas with the same --bundle argument.
```

Build the native backend and collect the corresponding sources/notices for its actual dependencies first; see [native instructions](native/README.md). Stage or commit release source before running `scripts/build.py`: it packages tracked Workbench files and the native source collection into `dist/AFM-Workbench-source.tar.gz` alongside the application. It refuses an incomplete or mismatched source collection. No experimental data enters this archive.

Build separately on each target OS. On macOS the application is `dist/AFM Workbench.app`. Windows native packaging remains unvalidated. CI builds on Mac and Linux, runs affected Python checks on pull requests and full Python checks on pushes/manual runs. Desktop renderer and packaging checks remain local; see [validation status](docs/validation.md) for executed evidence. Public release still needs signing/notarization and platform acceptance testing.

See [publishing](docs/publishing.md) for exporting a standalone source repository and the separate desktop-release requirements.

## Agent access

Configure an MCP client to launch this command with its own absolute paths:

```json
{
  "mcpServers": {
    "afm-workbench": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "afm_workbench", "--data-dir", "/path/to/workspace", "--mcp"]
    }
  }
}
```

Use the virtual environment's `Scripts/python.exe` on Windows. The GUI and MCP adapter dispatch into the same service and scientific functions. MCP has no arbitrary Python or SQL execution tool. Close one client before performing extensive writes from another; shared multi-user operation is not implemented.

## License

The combined application is [GPL-2.0-or-later](LICENSE). Earlier original code retains its [MIT grant](licenses/MIT-legacy.txt). Dependency licenses, source-distribution requirements and technical references are recorded in [third-party notices](docs/third-party.md). Private experimental data are not licensed for redistribution by this repository.

### 2D-material processing

Open a calibrated height image and choose **Prepare → More corrections → Fit up to 3 terrace planes**. This applies and saves an `auto_2d` correction to the current result. If opening the image already applied Auto level, undo that correction first to start from the original data. Terrace fitting optionally corrects scan-line background, fits up to three spatial planes, and excludes particles/edges from fitting. It subtracts one reference tilt across the whole image, preserving terrace height and tilt differences. Excluded features remain in the output. Open the fitted-plane details and choose **Inspect fitted planes** to examine the removed background and fitting assignments. Compare with **Original** and use **⌘/Ctrl Z** to undo the correction if needed. Plane assignments are model inferences, not identified materials.

The scan axis follows TIFF metadata, with a **Fast scan axis** override in More corrections. Switch off **Correct scan-line background** before applying the terrace correction to retain slow-axis shape: scan drift and real variation across a whole scan line are not always distinguishable. Strong coherent jumps are preserved for review. If terrace fitting fails, the saved recipe remains unchanged. Choose **3-point level**, or draw an **Area** as the reference and use **More corrections → Subtract reference plane**. See [methods and limitations](docs/science.md).

# Supported AFM input

An imported folder is one session. The browser retains every successfully imported image together, with acquisition, channel and direction filters inside that session. A filename's leading acquisition number is a browsing hint, not a new session or an instrument-assigned sample identifier.

## Park Systems TIFF

`afm_workbench.importers.load_scan` recognizes the file signature and private Park tags, regardless of extension. Supported input is little-endian classic TIFF with Park magic `0x0e031301`, version `0x01000001` or `0x01000002`, and a 2D mapped numerical image. The standard TIFF preview can have a different resolution and contains display colors: it is never used for numerical analysis. Park describes the distinction between preview and private numerical fields in its [FX40 manual, page 106](https://www.parksystems.com/content/dam/parksystems/product/manual/fx40/FX40-UMS-B3.1-EN%28FX40UserManual%2920221212.pdf).

The reader is original Python/NumPy code. Public field-layout references are [Park AFM viewer](https://github.com/mdendzik/Park-AFM-data-viewer/blob/master/AFMimage.m) and [Gwyddion's Park importer](https://github.com/cbuehler/gwyddion/blob/master/modules/file/psia.c). Neither implementation is copied or bundled. The latter is a format reference, not evidence of completed validation against Gwyddion.

| Field | Location | Interpretation |
| --- | --- | --- |
| Numerical payload | TIFF tag 50434 | Signed int16, signed int32 or float32; little-endian |
| Image header | TIFF tag 50435 | Version 1 minimum 356 bytes; version 2 minimum 580 bytes |
| Source channel | Header bytes 4–67 | UTF-16LE text |
| Width / height | Header offsets 100 / 104 | UInt32 numerical dimensions |
| Scan angle | Header offset 108 | Float64 degrees |
| Forward / slow direction / swapped axes | Offsets 128 / 132 / 136 | UInt32 flags |
| X / Y scan size | Offsets 140 / 148 | Float64 micrometers |
| X / Y offset | Offsets 156 / 164 | Float64 micrometers |
| Gain / scale / offset | Offsets 220 / 228 / 236 | Float64 calibration coefficients |
| Value unit | Bytes 244–259 | UTF-16LE text |
| Numerical data type | Offset 348 in version 2 | 0 = int16, 1 = int32, 2 = float32 |

Calibration uses `value = gain × (scale × raw + offset)`. Length values are converted to nanometers and degree values are labeled `°`; other declared units are retained. The complete transform, source/output units and pixel spacing are recorded. The reader rejects zero/non-finite vertical calibration, invalid lateral sizes, mismatched payload lengths, compressed/log/squared payload modes, unknown versions/data types, generic image TIFFs and spectroscopy/profile records. This release has a 512 MiB file and 32-million-pixel limit. NaN pixels remain missing and the validity mask is `finite(data)`; infinities and entirely missing images are rejected.

## Position and orientation

Park's [FX40 manual, page 100](https://www.parksystems.com/content/dam/parksystems/product/manual/fx40/FX40-UMS-B3.1-EN%28FX40UserManual%2920221212.pdf) defines X/Y offsets as the scan area's center relative to the XY scanner center. The imported `position` object therefore records `reference: "center"`, micrometer coordinates, the scan angle and `coordinate_frame: "scanner-relative"`. Scan width and height determine the footprint around that center. The application map is a footprint map derived from those fields. It does not establish stage coordinates, compensate stage motion or drift, or register/stitch image pixels.

Arrays retain their stored row and column order. Import does not flip, transpose, rotate, flatten or resample them. The metadata records the fast/slow directions, axis-swap flag and scan angle so this choice is explicit. Scan-line alignment uses rows in this stored array when axes are not swapped, and columns when they are swapped; angle and trace/retrace do not transpose the stored array. The interface exposes the metadata-derived choice and an explicit override. A swapped fast/slow direction does not remove the recorded X/Y offsets, extents or angle: these are independent fields in the [Park field-layout reference](https://github.com/mdendzik/Park-AFM-data-viewer/blob/master/AFMimage.m). The map uses those fields for an unregistered overview and labels swapped-axis scans explicitly; it does not infer flips or transposes from scan direction. Non-finite positions or angles have `position.calibrated: false` and appear in the map's separate unplaced gallery.

Importer 1.0.0 also marked swapped-axis positions uncalibrated even when coordinates were finite. The service now derives `map_footprint` for both GUI and MCP, recovering only this known legacy case (Park format/version/source, swapped-axis flag and original warning must match). Imported `position`, warnings, arrays and files remain untouched and inspectable. Importer 1.0.1 separates available footprint coordinates from unestablished pixel registration on new imports. Neither the footprint nor its semi-transparent preview is a registered or blended measurement.

An explicit `Forward`, `Backward`, `Trace` or `Retrace` filename label is used for browsing, with `direction_source: "filename label"`; otherwise the header flag is used. If filename and header disagree, both are preserved and a warning is shown. A filename is not evidence of physical image orientation.

The original binary image header is preserved as Base64, together with software/date fields, comments, extended XML, calibrated parameters and acquisition flags. Original TIFF files remain unchanged.

## Validation and limits

Run `python -m unittest discover -s tests -p test_importers.py -v` from the repository root. These tests create redistributable synthetic TIFF bytes with independently known arrays, calibration, dimensions, direction and position. They cover both header versions, all three supported data types, units, offset/rotation metadata, invalid pixels, conflicting direction labels, unsupported encodings, truncation and source immutability. No local research data is required.

The local research files supplied during development were read successfully and checked for unchanged SHA-256 hashes. Those files are private, ignored by version control and are not distribution fixtures. Successful parsing is not a completed comparison with XEI/Gwyddion or an independent instrument calibration. Additional Park variants and native Gwyddion `.gwy` files are not supported yet; unsupported files receive a visible import error rather than being interpreted as preview height data.

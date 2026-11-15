# Inspector workflow and design references

Design rationale prepared on 2026-11-10. The interface choices below are AI design decisions made within the user's authorized implementation scope (`origin: AI; claim_status: decision`). Their expected ergonomic benefit is an inference. The references describe established interfaces and individual reports of friction; they do not establish measured usability improvements in AFM Workbench. See [validation](validation.md) for checks actually executed.

## Implemented interaction

Organize the inspector around four stable, labeled tabs: **View**, **Prepare**, **Measure**, and **Record**. Preserve the active tab, control values and disclosure state while inspecting an image. Keep navigation reachable when the panel scrolls, and reveal the relevant tab when a canvas tool is selected.

| Task | Controls and purpose |
| --- | --- |
| View | Compact histogram; visible numeric minimum and maximum; one range track; **Auto / Full / Use region** actions together. Keep **Select region / Edit region** and **Clear** visible beside selection status. Identify these as display settings. |
| Prepare | Direct rectangle/brush and add/erase controls, mask coverage, overlay visibility and undo/redo. Keep include/exclude/ignore explicit. Put threshold masking and less common correction settings behind labeled disclosures. |
| Measure | Profile, step-height and roughness tools with controls appropriate to the selected measurement. Name reference regions clearly and keep results beside their action. |
| Record | Processing history, calibration, provenance and exports, with the source and saved result identifiable. |

Corrections save when applied, with a visible undo route. Show keyboard hints on common tools and retain an ordinary click route. Escape first cancels an active gesture, then leaves the drawing tool on a subsequent press. Use compact aligned rows and readable numbers, rather than reducing the canvas to accommodate an indefinitely expanding inspector. Formatting a number for display must not change its stored precision.

These choices aim to reduce repeated scrolling and mode ambiguity during substrate selection, leveling, flake-step measurement and roughness inspection. They do not add a physical interpretation to a fitted surface or turn contrast adjustment into a numerical transformation.

## Canvas interaction revision, 2026-11-14

The user requested restoration of contrast-region selection and refinement of canvas mouse interaction (`origin: human; claim_status: decision`). The following implementation choices are AI design decisions within that scope; reduced mode switching and easier recovery are expected benefits, not measured usability outcomes.

Keep contrast selection visible in **View** and on the canvas. **C** or **Select region** activates rectangle contrast, applied immediately using full-resolution values. The completed outline survives corrections, undo, tool changes and inspector navigation while the image remains open. **Edit region** returns to Contrast; drag the region's interior to move it, or its edges and corner handles to resize it. **Use region** uses the contrast rectangle first, otherwise the measurement Area. **Clear** removes only the outline. The outline is temporary view state and is not restored when an image is reopened; the numeric display limits remain saved separately.

Keep navigation available alongside the active scientific tool: **Space + drag** and middle-button drag temporarily pan; **H** selects Pan. Scrolling or pinching zooms around the pointer, with visible zoom buttons, a magnification readout and **Fit**. **+ / −** zoom and **F** fits the image. The 100–1600% readout is relative to the fitted image, not source-pixel magnification. Selections retain their source-image coordinates under zoom and pan. Neither navigation nor contrast transforms numerical data.

Require a three-screen-pixel drag before replacing a selection, and reject flat rectangles. Escape, lost pointer capture and window blur cancel the active gesture while retaining the completed selection. These choices aim to make accidental clicks and interrupted drags recoverable.

The temporary hand gesture and **H** follow [Figma's documented canvas navigation](https://help.figma.com/hc/en-us/articles/15297425105303-Explore-design-files). [Photoshop's pan controls](https://helpx.adobe.com/photoshop/desktop/get-started/learn-the-basics/navigate-and-pan-images.html) also document temporary Space panning and visible zoom controls; its [zoom guidance](https://helpx.adobe.com/photoshop/desktop/get-started/learn-the-basics/zoom-images.html) provides a visible Fit action. These are interaction references, not evidence of AFM Workbench usability or identical behavior across products.

## Established interface references

The following are documented product behaviors, not claims that a whole product should be copied.

| Reference | Pattern informing the proposal |
| --- | --- |
| [Gwyddion: false color mapping](https://gwyddion.net/documentation/user-guide-en/color-map.html) | Numeric, histogram and selected-area range controls; explicit separation of color mapping from numerical data. |
| [ImageJ: brightness and contrast](https://imagej.net/ij/docs/guide/146-28.html) | Histogram, interactive limits and automatic or selection-based display optimization. |
| [napari: image controls](https://napari.org/stable/howtos/layers/image.html) | Paired contrast limits and controls that follow the selected image layer. |
| [napari: label editing](https://napari.org/stable/howtos/layers/labels.html) | Distinct painting, erasing and navigation modes with keyboard access. |
| [Lightroom Classic: workspace](https://helpx.adobe.com/lightroom-classic/desktop/workspace/workspace-basics.html) | Collapsible panels and optional Solo mode, keeping the image central. |
| [Figma: properties sidebar](https://help.figma.com/hc/en-us/articles/360039832014-Design-prototype-and-explore-layer-properties-in-the-right-sidebar) | Contextual properties beside the canvas. |
| [Blender: sidebar guidelines](https://developer.blender.org/docs/features/interface/human_interface_guidelines/sidebar_tabs/) | Few workflow-oriented tabs, avoiding excessive tab switching. |
| [VS Code: keyboard shortcuts](https://code.visualstudio.com/docs/configure/keybindings) | Discoverable commands and visible keyboard alternatives. |

## Community feedback and resulting design inferences

These dated public reports are qualitative evidence of specific users' experiences. They are not representative surveys or current defect audits. The last column is our design inference.

| Public report | Reported friction | AFM implication |
| --- | --- | --- |
| [napari #5127](https://github.com/napari/napari/issues/5127), opened 2022-09-23 | Small floating-point ranges were difficult to adjust; contributors also reported that users did not discover numeric controls behind right-click. | Keep numeric limits visible and support appropriate precision for narrow ranges and large offsets. |
| [napari #3291](https://github.com/napari/napari/issues/3291), opened 2021-08-30 | Unused control space accompanied a clipped layer list requiring scrolling. | Avoid fixed empty panel space; check compact window sizes. |
| [Lightroom develop controls discussion](https://community.adobe.com/questions-675/develop-controls-suggestion-954446), 2021-04-28 | Repeated scrolling was tedious in high-volume work. One respondent preferred Solo mode; the requester found repeated opening and closing tedious too. | Use stable task navigation and compact controls; do not require a forced accordion for every action. |
| [Lightroom Solo-mode confusion](https://community.adobe.com/questions-675/how-to-get-the-scroll-bar-back-on-the-lightroom-classic-develop-screen-935544), 2018-08-09 | A user wanted to restore multiple open panels after unexpected auto-collapse. | Preserve disclosure choices and avoid surprising panel closure. |
| [Figma sidebar feedback](https://forum.figma.com/suggest-a-feature-11/add-ability-to-hide-the-new-left-sidebar-55802), July 2026 | Users objected to redundant navigation taking horizontal space, particularly in split-screen work. | Preserve canvas area and avoid another navigation rail. |

## Verification targets

Check keyboard access, focus visibility, compact window heights, readable negative and narrow numeric ranges, direct mask tool state, and retained settings after panel updates. Check that display-only actions leave numerical results unchanged. Record executed checks separately from these targets in [validation](validation.md).

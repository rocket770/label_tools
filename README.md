# Custom Annotation Software

Annotation software for reviewing and editing segmentation masks on time-series `.tif` image stacks.

The tool is optimized for mask cleanup and correction workflows, including brush-based editing, fill, merge, split, eyedropper selection, and polygon-based relabeling.

This project is based on the original `label_tools` repository by Wenwen La:
<https://github.com/wenwenla/label_tools>

## Getting Started

Download the latest release here: https://github.com/rocket770/label_tools/releases/tag/Release

Launch the executable:

```text
main.exe
```

The application opens in a maximized windowed mode so the normal Windows title bar and taskbar remain visible.

## Loading Files

You can load data in either of these ways:

1. Drag and drop files into the application window.
2. Use `File -> load`.

Supported inputs:

- Image stack: `.tif`
- Mask stack: `.npz`

You can load a `.tif` and `.npz` together or separately. Once loaded, the current filenames appear in the left panel.

## Display Controls

The left panel contains the main display settings:

- `ColorMap`: sets the image colormap for the `.tif` layer
- `Normalize`: rescales the current image frame for higher contrast
- `Bigfish`: shows the app's rescaled high-contrast version of the loaded image stack
- `Mask`: toggles mask visibility
- `Tif`: toggles raw image visibility
- `Show Cell IDs`: draws the current mask label value inside each connected cell region

For many annotation tasks, a good default starting point is:

- `ColorMap`: `BONE`
- `Normalize`: enabled
- `Mask`: enabled
- `Tif`: enabled

When both `Mask` and `Tif` are enabled, the software overlays the label mask on top of the image.
When `Show Cell IDs` is enabled, disconnected regions that happen to share the same label are each annotated in-place, which makes duplicate-label problems easier to spot before cleanup.

## Interface Overview

### Status and Cursor Information

The left panel shows:

- Current cell count for the active frame
- Cursor position and label under the cursor in the format `x y label`
- Current frame index

When no mask is loaded, the label field shows `-` while hovering.

### Label Controls

The label section lets you:

- Select the target label ID used by editing tools
- Preview that label's display color
- See the formatted label text for the selected ID

The eyedropper tool can also set the current label directly from an existing mask region.

### Navigation

Frame navigation is available through:

- The left and right arrow buttons under the image
- The frame slider
- Keyboard left/right arrow shortcuts

## Multi-Editor

`multi-editor` applies supported edits across a frame range.

Controls:

- `multi-editor`: enable or disable range editing
- `L`: left frame index
- `R`: right frame index

Behavior:

- Brush editing uses the selected `L` to `R` range
- Fill uses the selected `L` to `R` range
- Merge uses the selected `L` to `R` range
- Split is always limited to the current frame and temporarily disables multi-editor while active
- Polygon currently applies to the current frame only

If multi-editor is off, `L` and `R` follow the current frame automatically.

## Tools

The `Tools` panel contains the current annotation modes:

- `Mouse`
- `Eraser`
- `Pen`
- `Fill`
- `Eyedropper`
- `Merge`
- `Split`
- `Polygon`

The `Tool Options` panel updates based on the selected tool, so you only see controls relevant to the active tool.

### Mouse

Use `Mouse` mode to pan your working area by drawing a selection rectangle over the image. If the selection is too small, the view resets to the full image extent.

### Eraser

Use `Eraser` to paint label `0` into the mask with a square brush.

Options:

- `Tool size`

### Pen

Use `Pen` to paint the currently selected label ID into the mask with a square brush.

Options:

- `Tool size`

### Fill

`Fill` flood-fills the clicked connected region with the selected label.

Behavior:

- On one frame when multi-editor is off
- Across the selected frame range when multi-editor is on

### Eyedropper

`Eyedropper` samples the clicked mask label and sets it as the active label.

Behavior:

- Clicking background does not change the selected label
- Clicking a labeled region updates the current label and color preview

### Merge

`Merge` combines one label into another.

Workflow:

1. Click the label you want to keep.
2. Click the second label you want to merge into it.

Behavior:

- Works on the current frame by default
- Can apply across the selected multi-editor frame range

### Split

`Split` divides a mask region using a drawn line and assigns a new free label ID.

Workflow:

1. Select `Split`
2. Click and drag across the object to define the split line
3. Release the mouse to apply the split

Behavior:

- Uses the current brush size as the split thickness
- Automatically assigns the next available label ID
- Works on the current frame only
- Disables multi-editor while the tool is active

Options:

- `Tool size`

### Polygon

`Polygon` applies the selected label inside a user-defined polygon.

Workflow:

1. Select `Polygon`
2. Left-click to place polygon points
3. Move near the first point to close and apply the polygon
4. Right-click to cancel the polygon in progress

Options:

- `Close distance`: how close the cursor must be to the first point to close the polygon
- `Preview outline`: shows or hides the live polygon overlay
- `Fill holes`: fills internal holes in the polygon region
- `Apply to`: `Background only`, `Existing masks only`, or `Both`

Current polygon safeguards:

- Self-intersecting polygons are rejected
- By default, polygon fill does not overwrite neighboring labels unless `Apply to` is set to `Both`

## Context Menu Actions

Right-clicking in the image view opens a context menu with:

- `Copy`
- `Paste`
- `Delete`

These actions operate on mask regions and are useful for quick local corrections.

## Mask Menu Actions

The top menu also includes `Masks -> Repair and Normalize IDs`.

This batch action relabels the full mask stack without changing the mask shapes themselves. It is intended for cases where:

- the same cell flips between different IDs from frame to frame
- two disconnected cells were given the same label in one frame

Behavior:

- Tracks connected cell regions across frames and keeps one consistent ID per cell when possible
- Prefers the label a cell used most often across the stack
- If multiple cells compete for the same preferred label, one keeps it and the others fall back to the next lowest available IDs
- Repairs duplicate disconnected same-label regions by assigning them separate IDs
- Runs as a single undoable operation

Tip:

- Turn on `Show Cell IDs` before or after running this action to quickly inspect whether IDs are now stable across frames.

## Zoom and Brush Behavior

Mouse wheel behavior depends on modifiers:

- `Scroll Wheel`: changes brush size
- `Ctrl + Scroll Wheel`: zooms in or out around the cursor position

Additional notes:

- The brush is square-shaped
- Brush size changes affect `Pen`, `Eraser`, and `Split`

## Saving and Undo

Saving:

- Use `Ctrl + S` or `File -> save`
- Masks are saved as compressed `.npz` files
- The save filename includes a timestamp
- Saving writes a new file rather than overwriting silently with the original name

Undo:

- Use `Ctrl + Z`
- The application keeps a limited undo history of recent committed edits

## Building the App

This repository already includes simple build entrypoints for both Windows and macOS.

### Windows Build

Recommended steps from the project root:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
py -3 -m pip install --upgrade pip
py -3 -m pip install pyinstaller pyqt5 pillow numpy opencv-python-headless
.\build_windows.ps1
```

Output:

- `dist\main\main.exe`

Note:

- This is a folder-style PyInstaller build, so you should distribute the whole `dist\main\` folder, not only the `.exe`.

### macOS Build

Build this on a Mac from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller pyqt5 pillow numpy opencv-python-headless
chmod +x build_macos.sh
./build_macos.sh
```

Output:

- `dist/main.app`

Notes:

- macOS apps should be built on macOS rather than cross-compiled from Windows.
- If you plan to share the app outside your own machine, you may later want to add code signing and notarization.

## Keyboard Shortcuts

| Shortcut | Function |
|----------|----------|
| `Ctrl + S` | Save current mask stack |
| `Ctrl + Z` | Undo last committed edit |
| `Ctrl + M` | Toggle multi-editor |
| `Ctrl + E` | Select Eraser |
| `Ctrl + P` | Select Pen |
| `Ctrl + F` | Select Fill |
| `Left Arrow` | Previous frame |
| `Right Arrow` | Next frame |
| `Scroll Wheel` | Change brush size |
| `Ctrl + Scroll Wheel` | Zoom image |

## Recommended Annotation Workflow

1. Launch `main.exe`
2. Load your `.tif` image stack and `.npz` mask
3. Turn on both `Mask` and `Tif`
4. Turn on `Show Cell IDs` if you want to inspect per-cell label consistency directly on the image
5. Set `ColorMap` to `BONE` and enable `Normalize` if needed
6. Run `Masks -> Repair and Normalize IDs` if the imported mask stack does not keep the same cell IDs across frames
7. Choose the label you want to edit
8. Use `Pen`, `Eraser`, `Fill`, `Merge`, `Split`, `Eyedropper`, or `Polygon` as needed
9. Use multi-editor when you want the same correction across a frame range
10. Save regularly with `Ctrl + S`

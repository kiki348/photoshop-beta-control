---
name: photoshop-control
description: Use when Codex should control local Adobe Photoshop or Photoshop Beta on Windows for document creation, image placement, editable text/path work, layer operations, common edits, exports, batch workflows, or precise ExtendScript-based adjustments.
---

# Photoshop Control

Use this skill when the user asks Codex to edit, build, inspect, export, or automate work in local Adobe Photoshop or Photoshop Beta.

## Tools

Prefer the plugin MCP tools in this order:

1. `photoshop_status` to verify Photoshop COM is reachable and to inspect the active document.
2. `photoshop_find_progids` if status fails or times out, because it checks Windows registration without launching Photoshop.
3. `photoshop_open_image` to open a specific local image path.
4. `photoshop_create_document` to start a new canvas with a known size, background, and resolution.
5. `photoshop_place_image` to place a local image as a new positioned layer.
6. `photoshop_add_text_layer` for editable title, caption, label, and annotation text.
7. `photoshop_layer_ops` to list, select, rename, delete, show/hide, and style layers.
8. `photoshop_draw_paths` to create editable Photoshop paths from point data; use `stroke: true` only when a visible ink layer is needed.
9. `photoshop_adjust_image` for resize, crop, brightness, contrast, mild sharpening, and export.
10. `photoshop_texture_recolor` for realistic local recolors that need to preserve folds, highlights, shadows, and feathered edges.
11. `photoshop_apply_overlay` for prepared transparent edit layers that must be positioned precisely.
12. `photoshop_batch` for repeatable multi-step workflows.
13. `photoshop_export_active` to save a copy of the active document.
14. `photoshop_run_jsx` only for edits that require Photoshop ExtendScript beyond the safer tools.

## Operating Notes

- This is Windows-only and depends on Photoshop exposing a COM automation ProgID.
- The bridge tries `PHOTOSHOP_PROG_ID`, then `Photoshop.Application`, recent versioned ProgIDs, and `Photoshop.Application.Beta`.
- If Photoshop Beta is installed but not registered for COM, ask the user for the correct ProgID or use Adobe-supported automation setup.
- Use absolute file paths for inputs and outputs.
- For destructive-looking requests, save to a new output path unless the user explicitly wants to overwrite.
- For object recoloring, avoid flat color overlays. Prefer `photoshop_texture_recolor` with a tight polygon mask around the object so Photoshop receives a generated layer that keeps the source texture.
- Use `photoshop_apply_overlay` with `blendMode: "NORMAL"` for explicit visible prepared layers, and `blendMode: "COLOR"` only when preserving original luminosity is more important than color strength.
- For line art that must remain editable, prefer `photoshop_draw_paths`; it creates Photoshop path objects that can be edited with path/direct-selection tools.
- For office-style repetitive work, compose a `photoshop_batch` plan with document setup, layer creation, image placement, text labels, and export.
- Verify exported files exist after edits when possible.

## Example Requests

- "Open `C:\images\hero.png` in Photoshop and export a 1200px wide JPEG."
- "Increase contrast on the active Photoshop document and save a PNG copy."
- "Create a 1080p social post, place this product photo, add editable Chinese headline text, and export JPEG."
- "Draw a Fuji mountain line-art scene as editable Photoshop paths, then add a visible ink layer."
- "List layers, hide the old background, rename the AI overlay, and export a PSD copy."
- "Run this JSX against the active Photoshop document."

#!/usr/bin/env python3
"""Minimal MCP stdio server for controlling local Photoshop on Windows."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import colorsys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "photoshop_bridge.ps1"


TOOLS: list[dict[str, Any]] = [
    {
        "name": "photoshop_find_progids",
        "description": "List Photoshop-related COM ProgIDs registered on Windows without launching Photoshop.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_status",
        "description": "Check whether local Photoshop can be reached and report the active document.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "progId": {
                    "type": "string",
                    "description": "Optional COM ProgID override, for example Photoshop.Application.",
                },
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_open_image",
        "description": "Open an image file in Photoshop and return document information.",
        "inputSchema": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the image file."},
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_create_document",
        "description": "Create a new Photoshop document with a specified canvas size, background, and resolution.",
        "inputSchema": {
            "type": "object",
            "required": ["widthPx", "heightPx"],
            "properties": {
                "widthPx": {"type": "number", "minimum": 1},
                "heightPx": {"type": "number", "minimum": 1},
                "name": {"type": "string", "description": "Optional document name."},
                "resolution": {"type": "number", "minimum": 1, "description": "Pixels per inch. Defaults to 72."},
                "backgroundColor": {"type": "string", "description": "Optional #RRGGBB background. Defaults to white."},
                "transparent": {"type": "boolean", "description": "Create a transparent background instead of a filled background."},
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_adjust_image",
        "description": "Apply common edits to the active document, optionally opening and exporting a file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inputPath": {"type": "string", "description": "Optional absolute input path to open first."},
                "outputPath": {"type": "string", "description": "Optional absolute output path to save a copy."},
                "widthPx": {"type": "number", "description": "Optional target width in pixels."},
                "heightPx": {"type": "number", "description": "Optional target height in pixels."},
                "brightness": {"type": "integer", "minimum": -150, "maximum": 150},
                "contrast": {"type": "integer", "minimum": -50, "maximum": 100},
                "crop": {
                    "type": "object",
                    "description": "Optional crop rectangle in pixels.",
                    "properties": {
                        "left": {"type": "number"},
                        "top": {"type": "number"},
                        "right": {"type": "number"},
                        "bottom": {"type": "number"},
                    },
                    "required": ["left", "top", "right", "bottom"],
                    "additionalProperties": False,
                },
                "sharpen": {"type": "boolean", "description": "Apply a mild unsharp mask."},
                "jpegQuality": {"type": "integer", "minimum": 1, "maximum": 12},
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_texture_recolor",
        "description": "Recolor a selected region while preserving original texture, highlights, shadows, and feathered edges.",
        "inputSchema": {
            "type": "object",
            "required": ["targetColor", "maskPolygons"],
            "properties": {
                "targetColor": {"type": "string", "description": "Target color as #RRGGBB, for example #C81F2D."},
                "maskPolygons": {
                    "type": "array",
                    "description": "Polygon masks in document pixels. Each polygon is an array of {x,y} points.",
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["x", "y"],
                            "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                            "additionalProperties": False,
                        },
                    },
                },
                "layerName": {"type": "string", "description": "Name of the generated Photoshop layer."},
                "removeLayerNames": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional existing layer names to remove before recoloring.",
                },
                "opacity": {"type": "number", "minimum": 0, "maximum": 100},
                "featherPx": {"type": "number", "minimum": 0, "maximum": 20},
                "minMaskScore": {"type": "number", "minimum": 0, "maximum": 1},
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_apply_overlay",
        "description": "Paste a transparent overlay image into the active document, set blend mode/opacity, and align its visible bounds.",
        "inputSchema": {
            "type": "object",
            "required": ["overlayPath"],
            "properties": {
                "overlayPath": {"type": "string", "description": "Absolute path to a transparent overlay image."},
                "layerName": {"type": "string", "description": "Name for the pasted overlay layer."},
                "blendMode": {
                    "type": "string",
                    "enum": ["NORMAL", "COLOR", "HUE", "MULTIPLY", "SCREEN", "OVERLAY", "SOFTLIGHT"],
                    "description": "Photoshop blend mode. Defaults to NORMAL.",
                },
                "opacity": {"type": "number", "minimum": 0, "maximum": 100},
                "boundsLeftPx": {"type": "number", "description": "Target left pixel for the visible overlay bounds."},
                "boundsTopPx": {"type": "number", "description": "Target top pixel for the visible overlay bounds."},
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_place_image",
        "description": "Place a local image into the active document as a new layer, with optional position, scale, opacity, and blend mode.",
        "inputSchema": {
            "type": "object",
            "required": ["imagePath"],
            "properties": {
                "imagePath": {"type": "string", "description": "Absolute path to the image to place."},
                "layerName": {"type": "string"},
                "leftPx": {"type": "number", "description": "Optional target left pixel for placed layer bounds."},
                "topPx": {"type": "number", "description": "Optional target top pixel for placed layer bounds."},
                "widthPx": {"type": "number", "minimum": 1, "description": "Optional target width in pixels."},
                "heightPx": {"type": "number", "minimum": 1, "description": "Optional target height in pixels."},
                "opacity": {"type": "number", "minimum": 0, "maximum": 100},
                "blendMode": {
                    "type": "string",
                    "enum": ["NORMAL", "COLOR", "HUE", "MULTIPLY", "SCREEN", "OVERLAY", "SOFTLIGHT"],
                },
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_add_text_layer",
        "description": "Create an editable Photoshop text layer in the active document.",
        "inputSchema": {
            "type": "object",
            "required": ["text", "xPx", "yPx"],
            "properties": {
                "text": {"type": "string"},
                "layerName": {"type": "string"},
                "xPx": {"type": "number"},
                "yPx": {"type": "number"},
                "font": {"type": "string", "description": "Photoshop font PostScript name, for example MicrosoftYaHei-Bold."},
                "sizePx": {"type": "number", "minimum": 1},
                "color": {"type": "string", "description": "#RRGGBB text color."},
                "justification": {"type": "string", "enum": ["LEFT", "CENTER", "RIGHT"]},
                "opacity": {"type": "number", "minimum": 0, "maximum": 100},
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_layer_ops",
        "description": "List, select, rename, delete, hide/show, set opacity, or set blend mode for Photoshop layers.",
        "inputSchema": {
            "type": "object",
            "required": ["operation"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["list", "select", "rename", "delete", "show", "hide", "setOpacity", "setBlendMode"],
                },
                "layerName": {"type": "string", "description": "Target layer name for operations other than list."},
                "newName": {"type": "string", "description": "New layer name for rename."},
                "opacity": {"type": "number", "minimum": 0, "maximum": 100},
                "blendMode": {
                    "type": "string",
                    "enum": ["NORMAL", "COLOR", "HUE", "MULTIPLY", "SCREEN", "OVERLAY", "SOFTLIGHT"],
                },
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_draw_paths",
        "description": "Create editable Photoshop vector paths from line or polygon point data, optionally stroking them on visible ink layers.",
        "inputSchema": {
            "type": "object",
            "required": ["paths"],
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "points"],
                        "properties": {
                            "name": {"type": "string"},
                            "closed": {"type": "boolean"},
                            "stroke": {"type": "boolean", "description": "Stroke the path with the currently selected Photoshop brush."},
                            "strokeColor": {"type": "string", "description": "#RRGGBB foreground color used before stroking."},
                            "points": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["x", "y"],
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"},
                                        "leftX": {"type": "number"},
                                        "leftY": {"type": "number"},
                                        "rightX": {"type": "number"},
                                        "rightY": {"type": "number"},
                                        "smooth": {"type": "boolean"},
                                    },
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "additionalProperties": False,
                    },
                },
                "groupName": {"type": "string", "description": "Optional layer group for stroked ink layers."},
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_export_active",
        "description": "Save a copy of the active Photoshop document as PNG, JPEG, TIFF, or PSD.",
        "inputSchema": {
            "type": "object",
            "required": ["outputPath"],
            "properties": {
                "outputPath": {"type": "string", "description": "Absolute output path."},
                "jpegQuality": {"type": "integer", "minimum": 1, "maximum": 12},
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_run_jsx",
        "description": "Run custom ExtendScript JSX in Photoshop. Use only when the requested edit cannot be done by safer tools.",
        "inputSchema": {
            "type": "object",
            "required": ["jsx"],
            "properties": {
                "jsx": {"type": "string", "description": "ExtendScript source to execute in Photoshop."},
                "progId": {"type": "string", "description": "Optional COM ProgID override."},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 300},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "photoshop_batch",
        "description": "Run several Photoshop MCP operations in order. Useful for repeatable office/design workflows.",
        "inputSchema": {
            "type": "object",
            "required": ["steps"],
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["tool", "arguments"],
                        "properties": {
                            "tool": {"type": "string", "description": "Tool name such as photoshop_create_document."},
                            "arguments": {"type": "object"},
                        },
                        "additionalProperties": False,
                    },
                },
                "stopOnError": {"type": "boolean", "description": "Defaults to true."},
            },
            "additionalProperties": False,
        },
    },
]


def respond(message_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": message_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def bridge(action: str, args: dict[str, Any]) -> dict[str, Any]:
    prog_id = args.get("progId") or ""
    timeout_seconds = int(args.get("timeoutSeconds") or os.environ.get("PHOTOSHOP_MCP_TIMEOUT", "45"))
    bridge_args = dict(args)
    bridge_args.pop("progId", None)
    bridge_args.pop("timeoutSeconds", None)

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tmp:
        json.dump(bridge_args, tmp, ensure_ascii=False)
        tmp_path = tmp.name

    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(BRIDGE),
        "-Action",
        action,
        "-JsonFile",
        tmp_path,
    ]
    if prog_id:
        command.extend(["-ProgId", prog_id])

    try:
        completed = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Photoshop bridge timed out after {timeout_seconds}s. "
            "If Photoshop Beta is starting for the first time, open it manually once, then retry. "
            "You can also pass timeoutSeconds or set PHOTOSHOP_MCP_TIMEOUT."
        ) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    stdout = completed.stdout.strip()
    if completed.returncode != 0:
        detail = stdout or completed.stderr.strip() or f"PowerShell exited with {completed.returncode}"
        raise RuntimeError(detail)

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Bridge returned non-JSON output: {stdout}") from exc


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    action_by_tool = {
        "photoshop_find_progids": "find_progids",
        "photoshop_status": "status",
        "photoshop_open_image": "open_image",
        "photoshop_create_document": "create_document",
        "photoshop_adjust_image": "adjust_image",
        "photoshop_apply_overlay": "apply_overlay",
        "photoshop_place_image": "place_image",
        "photoshop_add_text_layer": "add_text_layer",
        "photoshop_layer_ops": "layer_ops",
        "photoshop_draw_paths": "draw_paths",
        "photoshop_export_active": "export_active",
        "photoshop_run_jsx": "run_jsx",
    }
    if name not in action_by_tool:
        if name == "photoshop_texture_recolor":
            result = texture_recolor(args)
            return {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                "isError": not bool(result.get("ok", False)),
            }
        if name == "photoshop_batch":
            result = batch(args)
            return {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                "isError": not bool(result.get("ok", False)),
            }
        raise ValueError(f"Unknown tool: {name}")

    result = bridge(action_by_tool[name], args)
    return {
        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
        "isError": not bool(result.get("ok", False)),
    }


def batch(args: dict[str, Any]) -> dict[str, Any]:
    stop_on_error = bool(args.get("stopOnError", True))
    results: list[dict[str, Any]] = []
    for index, step in enumerate(args.get("steps") or []):
        tool = str(step.get("tool") or "")
        if tool == "photoshop_batch":
            result = {"ok": False, "error": "Nested photoshop_batch calls are not allowed."}
        else:
            try:
                raw = call_tool(tool, step.get("arguments") or {})
                text = raw["content"][0]["text"]
                result = json.loads(text)
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "error": str(exc)}
        results.append({"index": index, "tool": tool, "result": result})
        if stop_on_error and not result.get("ok", False):
            return {"ok": False, "stoppedAt": index, "results": results}
    return {"ok": all(item["result"].get("ok", False) for item in results), "results": results}


def parse_hex_color(value: str) -> tuple[int, int, int]:
    color = value.strip().lstrip("#")
    if len(color) != 6:
        raise ValueError("targetColor must be #RRGGBB.")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def texture_recolor(args: dict[str, Any]) -> dict[str, Any]:
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("photoshop_texture_recolor requires Pillow to be installed.") from exc

    target_r, target_g, target_b = parse_hex_color(str(args["targetColor"]))
    target_h, target_l, target_s = colorsys.rgb_to_hls(target_r / 255, target_g / 255, target_b / 255)
    feather = float(args.get("featherPx") if args.get("featherPx") is not None else 0.8)
    min_score = float(args.get("minMaskScore") if args.get("minMaskScore") is not None else 0.40)
    opacity = float(args.get("opacity") if args.get("opacity") is not None else 100)
    layer_name = str(args.get("layerName") or "Codex texture recolor")
    work_dir = Path(tempfile.mkdtemp(prefix="photoshop-recolor-"))
    base_path = work_dir / "active_base.png"
    overlay_path = work_dir / "texture_recolor_overlay.png"

    remove_names = [str(name) for name in args.get("removeLayerNames") or [] if str(name)]
    if remove_names:
        quoted = json.dumps(remove_names)
        remove_jsx = f"""
var __names = {quoted};
if (app.documents.length < 1) {{ throw new Error("No document."); }}
var __doc = app.activeDocument;
var __removed = 0;
for (var __i = __doc.layers.length - 1; __i >= 0; __i--) {{
  var __layer = __doc.layers[__i];
  for (var __n = 0; __n < __names.length; __n++) {{
    if (__layer.name === __names[__n]) {{
      __layer.remove();
      __removed++;
      break;
    }}
  }}
}}
"removed " + __removed;
"""
        bridge("run_jsx", {**args, "jsx": remove_jsx})

    export_result = bridge("export_active", {**args, "outputPath": str(base_path)})
    if not export_result.get("ok"):
        return export_result

    source = Image.open(base_path).convert("RGBA")
    width, height = source.size
    shape = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(shape)
    for polygon in args["maskPolygons"]:
        points = [(float(point["x"]), float(point["y"])) for point in polygon]
        if len(points) >= 3:
            draw.polygon(points, fill=255)
    if feather > 0:
        shape = shape.filter(ImageFilter.GaussianBlur(feather))

    mask = Image.new("L", (width, height), 0)
    mask_pixels = mask.load()
    shape_pixels = shape.load()
    source_pixels = source.load()
    for y in range(height):
        for x in range(width):
            region = shape_pixels[x, y] / 255.0
            if region <= 0:
                continue
            red, green, blue, alpha = source_pixels[x, y]
            if alpha == 0:
                continue
            rf, gf, bf = red / 255, green / 255, blue / 255
            hue, sat, val = colorsys.rgb_to_hsv(rf, gf, bf)
            hue_deg = hue * 360
            redish_hue = hue_deg >= 320 or hue_deg <= 25 or 280 <= hue_deg <= 320
            hue_score = 1.0 if redish_hue else 0.0
            red_green = max(0.0, min(1.0, ((red - green) + 28) / 82.0))
            blue_green = max(0.0, min(1.0, ((blue - green) + 38) / 82.0))
            bright = max(0.0, min(1.0, (val - 0.32) / 0.45))
            score = 0.42 * hue_score + 0.28 * red_green + 0.18 * blue_green + 0.12 * bright
            if score > min_score:
                strength = min(1.0, max(0.35, (score - (min_score - 0.10)) / 0.55))
                mask_pixels[x, y] = int(255 * region * strength)
    mask = mask.filter(ImageFilter.MaxFilter(3))
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(max(0.1, feather * 0.8)))
    mask = ImageChops.multiply(mask, shape)
    bbox = mask.getbbox()
    if not bbox:
        raise RuntimeError("Texture recolor mask is empty. Check maskPolygons or minMaskScore.")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_pixels = overlay.load()
    mask_pixels = mask.load()
    target_l_boost = max(0.0, min(1.0, target_l))
    for y in range(height):
        for x in range(width):
            alpha = mask_pixels[x, y]
            if alpha == 0:
                continue
            red, green, blue, _ = source_pixels[x, y]
            rf, gf, bf = red / 255, green / 255, blue / 255
            _, lightness, saturation = colorsys.rgb_to_hls(rf, gf, bf)
            new_s = min(0.96, max(target_s * 0.88, saturation * 1.24 + 0.12))
            new_l = 0.04 + (lightness**1.02) * (0.52 + target_l_boost * 0.18)
            if lightness > 0.72:
                new_l = min(0.82, 0.58 + (lightness - 0.72) * 0.36 + target_l_boost * 0.05)
                new_s *= 0.92
            if lightness < 0.42:
                new_l *= 0.88
                new_s = min(0.98, new_s * 1.03)
            nr, ng, nb = colorsys.hls_to_rgb(target_h, new_l, new_s)
            luminance = 0.2126 * rf + 0.7152 * gf + 0.0722 * bf
            softness = 0.08
            nr = nr * (1 - softness) + luminance * softness
            ng = ng * (1 - softness) + luminance * softness
            nb = nb * (1 - softness) + luminance * softness
            overlay_pixels[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), alpha)
    overlay.save(overlay_path)

    apply_result = bridge(
        "apply_overlay",
        {
            **args,
            "overlayPath": str(overlay_path),
            "layerName": layer_name,
            "blendMode": "NORMAL",
            "opacity": opacity,
            "boundsLeftPx": bbox[0],
            "boundsTopPx": bbox[1],
        },
    )
    apply_result["generatedOverlayPath"] = str(overlay_path)
    apply_result["baseExportPath"] = str(base_path)
    apply_result["maskBounds"] = {"left": bbox[0], "top": bbox[1], "right": bbox[2], "bottom": bbox[3]}
    return apply_result


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    message_id = message.get("id")

    if method == "initialize":
        respond(
            message_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "photoshop-beta-control", "version": "0.1.0"},
            },
        )
    elif method == "tools/list":
        respond(message_id, {"tools": TOOLS})
    elif method == "tools/call":
        params = message.get("params") or {}
        try:
            respond(message_id, call_tool(params.get("name", ""), params.get("arguments") or {}))
        except Exception as exc:  # noqa: BLE001 - MCP should return structured tool errors.
            respond(
                message_id,
                {"content": [{"type": "text", "text": str(exc)}], "isError": True},
            )
    elif method in {"notifications/initialized", "notifications/cancelled"}:
        return
    elif method == "ping":
        respond(message_id, {})
    else:
        respond(message_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except Exception as exc:  # noqa: BLE001
            respond(None, error={"code": -32700, "message": str(exc)})


if __name__ == "__main__":
    main()

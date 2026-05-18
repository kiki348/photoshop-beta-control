param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("find_progids", "status", "run_jsx", "open_image", "create_document", "adjust_image", "apply_overlay", "place_image", "add_text_layer", "layer_ops", "draw_paths", "export_active")]
  [string]$Action,

  [string]$JsonFile,
  [string]$Json = "{}",
  [string]$ProgId
)

$ErrorActionPreference = "Stop"

function Write-JsonResult($Value) {
  $Value | ConvertTo-Json -Depth 20 -Compress
}

function Read-Payload {
  if ($JsonFile) {
    return Get-Content -Raw -LiteralPath $JsonFile | ConvertFrom-Json
  }
  return $Json | ConvertFrom-Json
}

function Get-PhotoshopApplication {
  $candidates = @()
  if ($ProgId) { $candidates += $ProgId }
  if ($env:PHOTOSHOP_PROG_ID) { $candidates += $env:PHOTOSHOP_PROG_ID }
  try {
    $candidates += @(Find-PhotoshopProgIds | ForEach-Object { $_.progId })
  } catch {}
  $candidates += @(
    "Photoshop.Application",
    "Photoshop.Application.BETA",
    "Photoshop.Application.BETA.1",
    "Photoshop.Application.2026",
    "Photoshop.Application.2025",
    "Photoshop.Application.2024",
    "Photoshop.Application.2023",
    "Photoshop.Application.Beta"
  )
  $candidates = $candidates | Where-Object { $_ } | Select-Object -Unique

  $errors = @()
  foreach ($candidate in $candidates) {
    try {
      $app = [Runtime.InteropServices.Marshal]::GetActiveObject($candidate)
      return [pscustomobject]@{ App = $app; ProgId = $candidate; Attached = $true }
    } catch {
      try {
        $app = New-Object -ComObject $candidate
        return [pscustomobject]@{ App = $app; ProgId = $candidate; Attached = $false }
      } catch {
        $errors += "${candidate}: $($_.Exception.Message)"
      }
    }
  }

  throw "Could not attach to Photoshop COM. Tried: $($candidates -join ', '). Errors: $($errors -join ' | ')"
}

function Find-PhotoshopProgIds {
  $roots = @("Registry::HKEY_CLASSES_ROOT")
  $items = @()
  foreach ($root in $roots) {
    $keys = Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue |
      Where-Object { $_.PSChildName -like "Photoshop.Application*" }
    foreach ($key in $keys) {
      $clsid = $null
      $server = $null
      try {
        $clsid = (Get-Item -LiteralPath (Join-Path $key.PSPath "CLSID") -ErrorAction Stop).GetValue("")
      } catch {}
      if ($clsid) {
        try {
          $server = (Get-Item -LiteralPath "Registry::HKEY_CLASSES_ROOT\CLSID\$clsid\LocalServer32" -ErrorAction Stop).GetValue("")
        } catch {}
      }
      $items += [pscustomobject]@{
        progId = $key.PSChildName
        clsid = $clsid
        localServer = $server
      }
    }
  }
  return $items
}

function Invoke-PhotoshopJsx($App, [string]$Jsx) {
  return $App.DoJavaScript($Jsx)
}

function ConvertTo-JsLiteral($Value) {
  return ($Value | ConvertTo-Json -Depth 20 -Compress)
}

$docInfoJsx = @'
function __psEsc(v) {
  return String(v).replace(/\\/g, "\\\\").replace(/"/g, "\\\"").replace(/\r/g, "\\r").replace(/\n/g, "\\n");
}
function __psDocInfo() {
  var appName = __psEsc(app.name);
  var appVersion = __psEsc(app.version);
  var count = app.documents.length;
  var json = '{"appName":"' + appName + '","appVersion":"' + appVersion + '","documentCount":' + count;
  if (count > 0) {
    var doc = app.activeDocument;
    json += ',"activeDocument":{';
    json += '"name":"' + __psEsc(doc.name) + '"';
    json += ',"widthPx":' + Number(doc.width.as("px"));
    json += ',"heightPx":' + Number(doc.height.as("px"));
    json += ',"resolution":' + Number(doc.resolution);
    json += ',"mode":"' + __psEsc(doc.mode) + '"';
    json += '}';
  }
  json += '}';
  return json;
}
__psDocInfo();
'@

function New-SaveJsx([string]$OutputPath, [int]$JpegQuality) {
  $payload = [pscustomobject]@{
    outputPath = $OutputPath
    jpegQuality = $JpegQuality
  }
  $literal = ConvertTo-JsLiteral $payload
  return @"
var __psParams = $literal;
function __psExt(path) {
  var m = String(path).match(/\.([^.\\\/]+)$/);
  return m ? m[1].toLowerCase() : "";
}

$blendModeJsx = @'
function __psSetBlendMode(layer, blendMode) {
  var mode = String(blendMode || "NORMAL").toUpperCase();
  if (mode === "NORMAL") {
    layer.blendMode = BlendMode.NORMAL;
  } else if (mode === "HUE") {
    layer.blendMode = BlendMode.HUE;
  } else if (mode === "MULTIPLY") {
    layer.blendMode = BlendMode.MULTIPLY;
  } else if (mode === "SCREEN") {
    layer.blendMode = BlendMode.SCREEN;
  } else if (mode === "OVERLAY") {
    layer.blendMode = BlendMode.OVERLAY;
  } else if (mode === "SOFTLIGHT") {
    layer.blendMode = BlendMode.SOFTLIGHT;
  } else if (mode === "COLOR") {
    layer.blendMode = BlendMode.COLORBLEND;
  } else {
    layer.blendMode = BlendMode.NORMAL;
  }
}
'@

$colorHelpersJsx = @'
function __psHexToColor(hex) {
  var value = String(hex || "#000000").replace("#", "");
  if (value.length !== 6) { throw new Error("Color must be #RRGGBB: " + hex); }
  var c = new SolidColor();
  c.rgb.red = parseInt(value.substr(0, 2), 16);
  c.rgb.green = parseInt(value.substr(2, 2), 16);
  c.rgb.blue = parseInt(value.substr(4, 2), 16);
  return c;
}
'@
function __psSaveCopy(path, jpegQuality) {
  var file = new File(path);
  var ext = __psExt(path);
  if (ext === "jpg" || ext === "jpeg") {
    var jpg = new JPEGSaveOptions();
    jpg.quality = jpegQuality || 10;
    app.activeDocument.saveAs(file, jpg, true, Extension.LOWERCASE);
  } else if (ext === "png") {
    var png = new PNGSaveOptions();
    app.activeDocument.saveAs(file, png, true, Extension.LOWERCASE);
  } else if (ext === "tif" || ext === "tiff") {
    var tif = new TiffSaveOptions();
    app.activeDocument.saveAs(file, tif, true, Extension.LOWERCASE);
  } else if (ext === "psd") {
    var psd = new PhotoshopSaveOptions();
    app.activeDocument.saveAs(file, psd, true, Extension.LOWERCASE);
  } else {
    throw new Error("Unsupported output extension: " + ext);
  }
}
__psSaveCopy(__psParams.outputPath, __psParams.jpegQuality);
$docInfoJsx
"@
}

try {
  $payload = Read-Payload
  if ($Action -eq "find_progids") {
    Write-JsonResult ([pscustomobject]@{
      ok = $true
      action = $Action
      progIds = @(Find-PhotoshopProgIds)
    })
    exit 0
  }

  $connection = Get-PhotoshopApplication
  $app = $connection.App
  $result = $null

  switch ($Action) {
    "status" {
      $result = Invoke-PhotoshopJsx $app $docInfoJsx
    }
    "run_jsx" {
      if (-not $payload.jsx) { throw "run_jsx requires a jsx string." }
      $result = Invoke-PhotoshopJsx $app ([string]$payload.jsx)
    }
    "open_image" {
      if (-not $payload.path) { throw "open_image requires path." }
      $literal = ConvertTo-JsLiteral ([pscustomobject]@{ path = [string]$payload.path })
      $jsx = @"
var __psParams = $literal;
var __psFile = new File(__psParams.path);
if (!__psFile.exists) { throw new Error("Input file does not exist: " + __psParams.path); }
app.open(__psFile);
$docInfoJsx
"@
      $result = Invoke-PhotoshopJsx $app $jsx
    }
    "create_document" {
      if (-not $payload.widthPx -or -not $payload.heightPx) { throw "create_document requires widthPx and heightPx." }
      $literal = ConvertTo-JsLiteral $payload
      $jsx = @"
var __psParams = $literal;
$colorHelpersJsx
var __psName = __psParams.name || "Codex Photoshop Document";
var __psResolution = Number(__psParams.resolution || 72);
var __psFill = __psParams.transparent ? DocumentFill.TRANSPARENT : DocumentFill.WHITE;
var __psDoc = app.documents.add(
  UnitValue(Number(__psParams.widthPx), "px"),
  UnitValue(Number(__psParams.heightPx), "px"),
  __psResolution,
  __psName,
  NewDocumentMode.RGB,
  __psFill
);
if (__psParams.backgroundColor && !__psParams.transparent) {
  app.foregroundColor = __psHexToColor(__psParams.backgroundColor);
  __psDoc.selection.selectAll();
  __psDoc.selection.fill(app.foregroundColor, ColorBlendMode.NORMAL, 100, false);
  __psDoc.selection.deselect();
  __psDoc.activeLayer.name = "background";
}
$docInfoJsx
"@
      $result = Invoke-PhotoshopJsx $app $jsx
    }
    "adjust_image" {
      $literal = ConvertTo-JsLiteral $payload
      $saveJsx = ""
      if ($payload.outputPath) {
        $quality = if ($payload.jpegQuality) { [int]$payload.jpegQuality } else { 10 }
        $saveJsx = New-SaveJsx ([string]$payload.outputPath) $quality
      } else {
        $saveJsx = $docInfoJsx
      }
      $jsx = @"
var __psParams = $literal;
if (__psParams.inputPath) {
  var __psInput = new File(__psParams.inputPath);
  if (!__psInput.exists) { throw new Error("Input file does not exist: " + __psParams.inputPath); }
  app.open(__psInput);
}
if (app.documents.length < 1) { throw new Error("No active Photoshop document."); }
var __psDoc = app.activeDocument;
if (__psParams.crop) {
  __psDoc.crop([
    UnitValue(__psParams.crop.left, "px"),
    UnitValue(__psParams.crop.top, "px"),
    UnitValue(__psParams.crop.right, "px"),
    UnitValue(__psParams.crop.bottom, "px")
  ]);
}
if (__psParams.widthPx || __psParams.heightPx) {
  var __psW = __psParams.widthPx ? UnitValue(__psParams.widthPx, "px") : undefined;
  var __psH = __psParams.heightPx ? UnitValue(__psParams.heightPx, "px") : undefined;
  __psDoc.resizeImage(__psW, __psH, undefined, ResampleMethod.BICUBICSHARPER);
}
if (__psParams.brightness !== undefined || __psParams.contrast !== undefined) {
  __psDoc.activeLayer.adjustBrightnessContrast(__psParams.brightness || 0, __psParams.contrast || 0);
}
if (__psParams.sharpen) {
  __psDoc.activeLayer.applyUnSharpMask(80, 1.0, 0);
}
$saveJsx
"@
      $result = Invoke-PhotoshopJsx $app $jsx
    }
    "export_active" {
      if (-not $payload.outputPath) { throw "export_active requires outputPath." }
      $quality = if ($payload.jpegQuality) { [int]$payload.jpegQuality } else { 10 }
      $result = Invoke-PhotoshopJsx $app (New-SaveJsx ([string]$payload.outputPath) $quality)
    }
    "apply_overlay" {
      if (-not $payload.overlayPath) { throw "apply_overlay requires overlayPath." }
      $literal = ConvertTo-JsLiteral $payload
      $jsx = @"
var __psParams = $literal;
$blendModeJsx
if (app.documents.length < 1) { throw new Error("No active target document."); }
var __psTarget = app.activeDocument;
var __psOverlayFile = new File(__psParams.overlayPath);
if (!__psOverlayFile.exists) { throw new Error("Overlay file does not exist: " + __psParams.overlayPath); }
var __psOverlayDoc = app.open(__psOverlayFile);
__psOverlayDoc.selection.selectAll();
__psOverlayDoc.selection.copy();
__psOverlayDoc.close(SaveOptions.DONOTSAVECHANGES);
app.activeDocument = __psTarget;
__psTarget.paste();
var __psLayer = __psTarget.activeLayer;
__psLayer.name = __psParams.layerName || "Codex overlay";
__psSetBlendMode(__psLayer, __psParams.blendMode);
if (__psParams.opacity !== undefined) { __psLayer.opacity = Number(__psParams.opacity); }
if (__psParams.boundsLeftPx !== undefined || __psParams.boundsTopPx !== undefined) {
  var __psBounds = __psLayer.bounds;
  var __psLeft = Number(__psBounds[0].as("px"));
  var __psTop = Number(__psBounds[1].as("px"));
  var __psTargetLeft = (__psParams.boundsLeftPx !== undefined) ? Number(__psParams.boundsLeftPx) : __psLeft;
  var __psTargetTop = (__psParams.boundsTopPx !== undefined) ? Number(__psParams.boundsTopPx) : __psTop;
  __psLayer.translate(UnitValue(__psTargetLeft - __psLeft, "px"), UnitValue(__psTargetTop - __psTop, "px"));
}
$docInfoJsx
"@
      $result = Invoke-PhotoshopJsx $app $jsx
    }
    "place_image" {
      if (-not $payload.imagePath) { throw "place_image requires imagePath." }
      $literal = ConvertTo-JsLiteral $payload
      $jsx = @"
var __psParams = $literal;
$blendModeJsx
if (app.documents.length < 1) { throw new Error("No active target document."); }
var __psTarget = app.activeDocument;
var __psImageFile = new File(__psParams.imagePath);
if (!__psImageFile.exists) { throw new Error("Image file does not exist: " + __psParams.imagePath); }
var __psImageDoc = app.open(__psImageFile);
__psImageDoc.selection.selectAll();
__psImageDoc.selection.copy();
__psImageDoc.close(SaveOptions.DONOTSAVECHANGES);
app.activeDocument = __psTarget;
__psTarget.paste();
var __psLayer = __psTarget.activeLayer;
__psLayer.name = __psParams.layerName || "Codex placed image";
__psSetBlendMode(__psLayer, __psParams.blendMode);
if (__psParams.opacity !== undefined) { __psLayer.opacity = Number(__psParams.opacity); }
var __psBounds = __psLayer.bounds;
var __psLeft = Number(__psBounds[0].as("px"));
var __psTop = Number(__psBounds[1].as("px"));
var __psRight = Number(__psBounds[2].as("px"));
var __psBottom = Number(__psBounds[3].as("px"));
var __psWidth = __psRight - __psLeft;
var __psHeight = __psBottom - __psTop;
if (__psParams.widthPx || __psParams.heightPx) {
  var __psTargetW = __psParams.widthPx ? Number(__psParams.widthPx) : (__psWidth * Number(__psParams.heightPx) / __psHeight);
  var __psTargetH = __psParams.heightPx ? Number(__psParams.heightPx) : (__psHeight * Number(__psParams.widthPx) / __psWidth);
  __psLayer.resize((__psTargetW / __psWidth) * 100, (__psTargetH / __psHeight) * 100, AnchorPosition.TOPLEFT);
  __psBounds = __psLayer.bounds;
  __psLeft = Number(__psBounds[0].as("px"));
  __psTop = Number(__psBounds[1].as("px"));
}
if (__psParams.leftPx !== undefined || __psParams.topPx !== undefined) {
  var __psTargetLeft = (__psParams.leftPx !== undefined) ? Number(__psParams.leftPx) : __psLeft;
  var __psTargetTop = (__psParams.topPx !== undefined) ? Number(__psParams.topPx) : __psTop;
  __psLayer.translate(UnitValue(__psTargetLeft - __psLeft, "px"), UnitValue(__psTargetTop - __psTop, "px"));
}
$docInfoJsx
"@
      $result = Invoke-PhotoshopJsx $app $jsx
    }
    "add_text_layer" {
      if (-not $payload.text) { throw "add_text_layer requires text." }
      $literal = ConvertTo-JsLiteral $payload
      $jsx = @"
var __psParams = $literal;
$colorHelpersJsx
if (app.documents.length < 1) { throw new Error("No active Photoshop document."); }
var __psDoc = app.activeDocument;
var __psLayer = __psDoc.artLayers.add();
__psLayer.kind = LayerKind.TEXT;
__psLayer.name = __psParams.layerName || "Codex text";
var __psText = __psLayer.textItem;
__psText.contents = String(__psParams.text);
__psText.position = [UnitValue(Number(__psParams.xPx), "px"), UnitValue(Number(__psParams.yPx), "px")];
if (__psParams.font) { __psText.font = String(__psParams.font); }
if (__psParams.sizePx) { __psText.size = UnitValue(Number(__psParams.sizePx), "px"); }
if (__psParams.color) { __psText.color = __psHexToColor(__psParams.color); }
var __psJust = String(__psParams.justification || "LEFT").toUpperCase();
if (__psJust === "CENTER") { __psText.justification = Justification.CENTER; }
else if (__psJust === "RIGHT") { __psText.justification = Justification.RIGHT; }
else { __psText.justification = Justification.LEFT; }
if (__psParams.opacity !== undefined) { __psLayer.opacity = Number(__psParams.opacity); }
$docInfoJsx
"@
      $result = Invoke-PhotoshopJsx $app $jsx
    }
    "layer_ops" {
      if (-not $payload.operation) { throw "layer_ops requires operation." }
      $literal = ConvertTo-JsLiteral $payload
      $jsx = @"
var __psParams = $literal;
$blendModeJsx
function __psEsc(v) {
  return String(v).replace(/\\/g, "\\\\").replace(/"/g, "\\\"").replace(/\r/g, "\\r").replace(/\n/g, "\\n");
}
function __psLayerKind(layer) {
  try { return String(layer.kind); } catch (e) { return layer.typename; }
}
function __psListLayers(container, prefix, out) {
  for (var i = 0; i < container.layers.length; i++) {
    var layer = container.layers[i];
    var path = prefix ? prefix + "/" + layer.name : layer.name;
    out.push('{"name":"' + __psEsc(layer.name) + '","path":"' + __psEsc(path) + '","type":"' + __psEsc(layer.typename) + '","kind":"' + __psEsc(__psLayerKind(layer)) + '","visible":' + layer.visible + ',"opacity":' + Number(layer.opacity) + '}');
    if (layer.typename === "LayerSet") { __psListLayers(layer, path, out); }
  }
}
function __psFindLayer(container, name) {
  for (var i = 0; i < container.layers.length; i++) {
    var layer = container.layers[i];
    if (layer.name === name) { return layer; }
    if (layer.typename === "LayerSet") {
      var found = __psFindLayer(layer, name);
      if (found) { return found; }
    }
  }
  return null;
}
if (app.documents.length < 1) { throw new Error("No active Photoshop document."); }
var __psDoc = app.activeDocument;
var __psOperation = String(__psParams.operation);
if (__psOperation === "list") {
  var __psOut = [];
  __psListLayers(__psDoc, "", __psOut);
  "[" + __psOut.join(",") + "]";
} else {
  if (!__psParams.layerName) { throw new Error("layerName is required for operation " + __psOperation); }
  var __psLayer = __psFindLayer(__psDoc, String(__psParams.layerName));
  if (!__psLayer) { throw new Error("Layer not found: " + __psParams.layerName); }
  if (__psOperation === "select") {
    __psDoc.activeLayer = __psLayer;
  } else if (__psOperation === "rename") {
    if (!__psParams.newName) { throw new Error("newName is required for rename."); }
    __psLayer.name = String(__psParams.newName);
  } else if (__psOperation === "delete") {
    __psLayer.remove();
  } else if (__psOperation === "show") {
    __psLayer.visible = true;
  } else if (__psOperation === "hide") {
    __psLayer.visible = false;
  } else if (__psOperation === "setOpacity") {
    __psLayer.opacity = Number(__psParams.opacity);
  } else if (__psOperation === "setBlendMode") {
    __psSetBlendMode(__psLayer, __psParams.blendMode);
  } else {
    throw new Error("Unsupported layer operation: " + __psOperation);
  }
  $docInfoJsx
}
"@
      $result = Invoke-PhotoshopJsx $app $jsx
    }
    "draw_paths" {
      if (-not $payload.paths) { throw "draw_paths requires paths." }
      $literal = ConvertTo-JsLiteral $payload
      $jsx = @"
var __psParams = $literal;
$colorHelpersJsx
if (app.documents.length < 1) { throw new Error("No active Photoshop document."); }
var __psDoc = app.activeDocument;
function __psRemovePathByName(name) {
  for (var i = __psDoc.pathItems.length - 1; i >= 0; i--) {
    if (__psDoc.pathItems[i].name === name) { __psDoc.pathItems[i].remove(); }
  }
}
function __psMakePath(pathSpec) {
  if (!pathSpec.points || pathSpec.points.length < 2) { throw new Error("Path requires at least two points: " + pathSpec.name); }
  var points = [];
  for (var i = 0; i < pathSpec.points.length; i++) {
    var p = pathSpec.points[i];
    var pt = new PathPointInfo();
    pt.kind = p.smooth ? PointKind.SMOOTHPOINT : PointKind.CORNERPOINT;
    pt.anchor = [Number(p.x), Number(p.y)];
    pt.leftDirection = [(p.leftX !== undefined ? Number(p.leftX) : Number(p.x)), (p.leftY !== undefined ? Number(p.leftY) : Number(p.y))];
    pt.rightDirection = [(p.rightX !== undefined ? Number(p.rightX) : Number(p.x)), (p.rightY !== undefined ? Number(p.rightY) : Number(p.y))];
    points.push(pt);
  }
  var sub = new SubPathInfo();
  sub.closed = !!pathSpec.closed;
  sub.operation = ShapeOperation.SHAPEXOR;
  sub.entireSubPath = points;
  __psRemovePathByName(pathSpec.name);
  var item = __psDoc.pathItems.add(pathSpec.name, [sub]);
  if (pathSpec.stroke) {
    app.foregroundColor = __psHexToColor(pathSpec.strokeColor || "#000000");
    var layer = __psDoc.artLayers.add();
    layer.name = pathSpec.name + " ink";
    item.strokePath(ToolType.BRUSH);
  }
  return item.name;
}
var __psCreated = [];
for (var __psI = 0; __psI < __psParams.paths.length; __psI++) {
  __psCreated.push(__psMakePath(__psParams.paths[__psI]));
}
'{"createdPaths":["' + __psCreated.join('","') + '"],"count":' + __psCreated.length + '}';
"@
      $result = Invoke-PhotoshopJsx $app $jsx
    }
  }

  Write-JsonResult ([pscustomobject]@{
    ok = $true
    action = $Action
    progId = $connection.ProgId
    attachedToRunningInstance = $connection.Attached
    photoshopResult = $result
  })
} catch {
  Write-JsonResult ([pscustomobject]@{
    ok = $false
    action = $Action
    error = $_.Exception.Message
  })
  exit 1
}

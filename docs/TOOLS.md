# MCP 工具说明

## 状态和文件

- `photoshop_find_progids`：不启动 Photoshop，只查注册表中的 ProgID。
- `photoshop_status`：连接 Photoshop 并返回当前文档状态。
- `photoshop_open_image`：打开本地图片。
- `photoshop_export_active`：导出当前文档到 PNG/JPEG/TIFF/PSD。

## 文档和图层

- `photoshop_create_document`：新建画布。
- `photoshop_place_image`：放置图片为新图层。
- `photoshop_add_text_layer`：添加可编辑文字层。
- `photoshop_layer_ops`：图层列表、选择、重命名、删除、显隐、透明度、混合模式。

## 设计编辑

- `photoshop_draw_paths`：从点数据创建可编辑路径。可选 `stroke: true` 用当前画笔描边。
- `photoshop_adjust_image`：裁切、缩放、亮度、对比度、锐化。
- `photoshop_texture_recolor`：局部换色，保留原图纹理。
- `photoshop_apply_overlay`：贴入透明叠加层并对齐。

## 高级能力

- `photoshop_batch`：按顺序执行多个工具。
- `photoshop_run_jsx`：执行自定义 JSX。建议只在结构化工具覆盖不到时使用。

## 路径绘制说明

`photoshop_draw_paths` 的点支持贝塞尔控制柄：

```json
{
  "x": 120,
  "y": 300,
  "leftX": 100,
  "leftY": 280,
  "rightX": 150,
  "rightY": 320,
  "smooth": true
}
```

如果不提供控制柄，会创建角点。

## 批处理说明

`photoshop_batch` 每一步都形如：

```json
{
  "tool": "photoshop_add_text_layer",
  "arguments": {
    "text": "Hello",
    "xPx": 100,
    "yPx": 100
  }
}
```

默认 `stopOnError: true`。如果希望某一步失败后继续，可传：

```json
{
  "stopOnError": false,
  "steps": []
}
```

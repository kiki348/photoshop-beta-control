# 使用示例

## 1. 新建画布并添加文字

对 Codex 说：

```text
用 Photoshop 新建一个 1920x1080 白底画布，左上角添加可编辑标题“新品上市”，底部添加小字“Codex 自动排版”，导出 JPG。
```

推荐工具组合：

1. `photoshop_status`
2. `photoshop_create_document`
3. `photoshop_add_text_layer`
4. `photoshop_export_active`

## 2. 放置图片并导出社媒图

```text
把 C:\images\product.png 放到 1080x1080 画布中央，加一个深色背景和中文标题，导出 PNG。
```

推荐工具组合：

1. `photoshop_create_document`
2. `photoshop_place_image`
3. `photoshop_add_text_layer`
4. `photoshop_export_active`

## 3. 创建可编辑线稿

```text
在 Photoshop 中画一幅富士山线稿，要求每条主线后续可编辑，不要只贴一张图。
```

推荐用 `photoshop_draw_paths` 创建 Photoshop 路径对象。路径可以在 Photoshop 的 Paths 面板里继续编辑。需要可见墨迹时设置 `stroke: true`，但要注意描出来的墨迹层是像素层。

## 4. 保留纹理的局部换色

```text
把当前图里的粉色蝴蝶结改成深红色，保留布料纹理、高光和阴影。
```

推荐用 `photoshop_texture_recolor`：

- 用 `maskPolygons` 描出目标区域。
- 设置 `targetColor`。
- 调低或调高 `featherPx` 控制边缘融合。
- 用 `removeLayerNames` 清理旧尝试层。

## 5. 批量工作流

`photoshop_batch` 可以把多个步骤串起来，例如：

```json
{
  "steps": [
    {
      "tool": "photoshop_create_document",
      "arguments": {
        "widthPx": 1920,
        "heightPx": 1080,
        "backgroundColor": "#111111",
        "name": "social-post"
      }
    },
    {
      "tool": "photoshop_add_text_layer",
      "arguments": {
        "text": "Codex 自动排版",
        "xPx": 120,
        "yPx": 180,
        "sizePx": 80,
        "color": "#ffffff"
      }
    },
    {
      "tool": "photoshop_export_active",
      "arguments": {
        "outputPath": "C:\\temp\\social-post.jpg",
        "jpegQuality": 10
      }
    }
  ]
}
```

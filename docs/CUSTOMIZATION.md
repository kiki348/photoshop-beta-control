# 自定义开发

## 结构

```text
scripts/mcp_server.py
```

负责 MCP 协议、工具 schema、参数入口、批处理和非 Photoshop 侧的辅助逻辑。

```text
scripts/photoshop_bridge.ps1
```

负责连接 Photoshop COM，并把结构化参数转换成 ExtendScript。

```text
skills/photoshop-control/SKILL.md
```

负责告诉 Codex 何时使用哪个工具。新增工具后要同步更新这里，否则 Codex 可能仍然倾向于直接写 JSX。

## 添加一个新工具

1. 在 `scripts/mcp_server.py` 的 `TOOLS` 里添加 schema。
2. 在 `call_tool` 的 `action_by_tool` 里绑定工具名和 action。
3. 在 `scripts/photoshop_bridge.ps1` 的 `ValidateSet` 里添加 action。
4. 在 PowerShell `switch ($Action)` 里实现 JSX。
5. 在 `docs/TOOLS.md` 和 `skills/photoshop-control/SKILL.md` 里补说明。
6. 用一个最小 JSON-RPC 请求验证 `tools/list` 能返回新工具。

## 设计建议

- 优先提供小而稳定的结构化工具。
- 把易错 Photoshop Action Manager 代码藏在 bridge 里，不要让 Codex 每次临时生成。
- 对会破坏原图的任务，默认新建图层或导出副本。
- 对可编辑交付物，优先保留文字层、路径、图层组和 PSD。
- 对生成式或不可预测任务，要求 Codex 先导出预览给用户确认。

## 可扩展方向

- 选区工具：矩形、椭圆、多边形、颜色范围。
- 调整图层：曲线、色相/饱和度、色阶。
- 智能对象：置入为智能对象、替换内容。
- 模板系统：把固定排版封装成 JSON 配方。
- 批量文件夹处理：读取目录、逐张打开、导出多规格。
- OCR/视觉定位：结合截图或图像识别生成更准确的蒙版点位。

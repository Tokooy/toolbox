# 共识 Agora

在 Toolbox 左侧选择 **共识 Agora**。首次使用时配置 Agent 角色与 DeepSeek API Key，即可上传文档、设定研讨目标并启动多轮讨论。发言会实时显示，引用可跳转到原文行号。工作台支持查看历史、停止研讨和导出 Markdown 报告。内置示例使用预置内容。

Agora 支持 HTML、纯文本、PDF、DOCX 和 XLSX。单文件上限为 100 MB 和 120 万字符，每次研讨最多选择 8 个文件，带行号的正文合计上限为 16 万字符。

整合版默认把提取正文、研讨历史、角色和 API Key 设置保存在 Toolbox 的 `data/agora/`。独立 Agora 继续使用它原来的数据卷。发起真实研讨时，选中的文档正文及相关发言会发送给 DeepSeek。

从源码运行时，按仓库根目录的 [启动说明](../../README_zh.md#一快速开始) 安装依赖并构建前端。Toolbox 会通过同一个端口提供 Agora 工作台和 API。

## 验证

在仓库根目录运行后端测试。

```bash
python -m unittest discover -s apps/agora/backend/tests -v
```

运行中的 Toolbox 可以通过 Playwright 验证侧栏、上传、流式发言及报告。默认使用端口 8080，也可以设置 `AGORA_URL` 指向整合版工作台。

```bash
cd apps/agora/tests
npm install
npx playwright install chromium
npm test
```

独立版的启动方式见 [Tokooy/agora](https://github.com/Tokooy/agora)。

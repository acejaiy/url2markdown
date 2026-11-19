# 导出目标适配器（高阶用户扩展点）

V1.1.0 起，GUI 不再把导出逻辑写死在按钮回调里，而是通过 `destinations/` 目录注册目标。

## 现有目标

| key | 文件 | GUI 文案 | 状态 |
| --- | --- | --- | --- |
| `local` | `local_files.py` | 保存为本地文件 | 已启用 |
| `siyuan` | `siyuan.py` | 剪藏至思源笔记（需用户复制笔记本 ID） | 已启用 |
| `obsidian` | `obsidian.py` | Obsidian（即将支持） | 预留入口，默认不显示勾选框 |

## 新增一个目标

1. 新建 `destinations/your_target.py`：

```python
from fetcher import Article
from .base import BaseDestination, ExportOptions
from .registry import register

@register
class YourTarget(BaseDestination):
    key = "your_target"
    label = "导出到我的工具"
    hint = "一句话说明"

    def is_ready(self):
        return True, ""

    def export(self, article: Article, category: str, options: ExportOptions) -> str:
        # 用 build_markdown(article, category) 拿到正文
        return "已完成"
```

2. 在 `destinations/__init__.py` 中导入你的模块（触发注册）。
3. 在 `config.py` 的 `DESTINATION_ORDER` 中加入 `"your_target"`。
4. GUI 会自动显示勾选框；默认值可在 `settings.py` 的 `DEFAULT_SETTINGS["destinations"]` 中添加。

## 思源目标的替换点

- API / 笔记本 ID / Token：`settings.py` 的 `siyuan` 配置段，GUI 中一次设定后持久化。
- 图片策略：`config.SIYUAN_UPLOAD_IMAGES`。默认保留原图 URL；开启后尝试上传到 `/api/asset/upload`。
- 同名文档：`config.SIYUAN_ADD_TIME_SUFFIX`。默认关闭，保持标题干净。
- 路径规则：`siyuan_client.SiYuanClient.doc_path()`，默认 `/网页剪藏/分类/标题`。

## 说明

旧版 `siyuan.py` 保留为按“笔记本名称”写入的参考实现，供 `main.py` / `exe_main.py` 使用；新版 GUI 使用 `siyuan_client.py` + `destinations/siyuan.py`，按“笔记本 ID”写入，避免改名后失效。

# 苹果发布会风格 PPT Skill

把讲稿制作成可编辑 PPTX：克制的蓝紫粉渐变、大数字、真实照片、淡入加轻微上移，并让每次点击对应口播。

![原创演示封面](examples/preview.png)

[下载三页可编辑动画演示](examples/apple-keynote-demo.pptx)

## 安装

将本仓库的 `apple-keynote-ppt` 文件夹复制到你的 Codex skills 目录：

- macOS / Linux：`~/.codex/skills/`
- Windows：`%USERPROFILE%\.codex\skills\`
- 设置了 `CODEX_HOME` 时，使用该目录下面的 `skills/`。

开始新对话后使用：

> 使用 $apple-keynote-ppt，把这份五分钟讲稿制作成苹果发布会风格的可编辑 PPTX，在教室 Windows 的 WPS / Office 中播放。页面顺序和讲稿一致，最后的主题页也要有点击动画。

## 结构

- `SKILL.md`：短入口，只加载必要步骤。
- `references/design.md`：配色、字体、版式和讲稿同步。
- `references/motion.md`：原生动画用法、故障排查和兼容性边界。
- `scripts/pptx_motion.py`：添加动画、检查对象和点击组，Python 3.10+ 标准库即可运行。
- `examples/`：原创三页可编辑演示、动画计划、可再生成的源码。

动画命令：

```bash
python apple-keynote-ppt/scripts/pptx_motion.py apply base.pptx result.pptx --steps examples/steps.json
python apple-keynote-ppt/scripts/pptx_motion.py audit result.pptx --steps examples/steps.json
python -m unittest discover -s tests -v
```

示例源码使用 `@oai/artifact-tool`；在已提供该库的 Codex 文档运行环境中运行。Skill 的设计方法可用于其他可编辑 PPTX 工具；动画脚本无需该库。使用不同的基础稿时，须修改计划里的对象名称。

示例文本、渐变和动画可编辑。静态预览显示所有内容，播放时按点击出现。文件结构检查已执行，未在 Windows Office / WPS 上实测；具体效果需用实际播放软件核验。

MIT 许可适用于本仓库原创代码和说明。本仓库不分发原历史演讲的第三方照片、用户个人资料或上游插件文件。方法受 Apple 发布演示的视觉风格启发，与 Apple 无官方关联。

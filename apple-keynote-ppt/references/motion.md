# 动画与检查

## 最小用法

Python 3.10+，脚本仅依赖标准库。在基础 PPTX 导出后添加原生 OOXML 动画，不调用 `python-pptx`。

```bash
python apple-keynote-ppt/scripts/pptx_motion.py audit base.pptx
python apple-keynote-ppt/scripts/pptx_motion.py apply base.pptx animated.pptx --steps steps.json
python apple-keynote-ppt/scripts/pptx_motion.py audit animated.pptx --steps steps.json
```

`steps.json` 的键是从 1 开始的页码，每个内层数组代表一次点击。数组中的第一个对象是点击触发，其余同时出现。名字对应 PPTX 的 `cNvPr.name`，图片也可用 `@picture1`、`@picture2`，按页面图片对象顺序编号，不是素材文件编号。

```json
{
  "1": [["reveal_subtitle"]],
  "2": [["reveal_number", "reveal_scope"]],
  "3": [["peace_line", "@picture1", "caption_left"], ["@picture2", "caption_right", "closing_sentence"]],
  "4": []
}
```

标题未列入计划，所以初始可见。结尾页不是例外：初始保留主题，点击1出现证据，点击2出现最后一句，下一次点击才换页。

默认：600ms 淡入、从下方 2.5% 页高轻移到原位、减速结束。可传 `--fade-only` 去掉位移，或 `--duration 500` 调整时长。`--replace` 明确替换计划涉及页的原有动画；未指定时遇到已有动画会停止。未列入计划的页不变。输出必须是新文件，避免覆盖原稿。

## 故障排查

1. `audit` 检查对象编号是否唯一、所有动画目标是否存在、计划的点击组是否与文件匹配。不要把图片序号当作对象编号，也不要只凭动画数量判断成功。
2. 在本次成品修复中，第7页第二张图片的对象编号与动画引用曾同步改成10。这是兼容性排查记录，不能证明“编号2必然有问题”。OOXML 的对象编号和动画时间节点编号属于不同范围，不要求两者互不重复。
3. 导出器可能重写对象编号。每次从基础稿重新导出后，按名称／图片别名重新生成动画，不能把上一次编号硬编码到新文件。
4. 在 WPS／PowerPoint 编辑模式看到全部内容是正常的。进入放映才能核验初始隐藏和点击顺序。重新打开最终文件，避免测到旧标签或缓存。
5. 逐页实测，尤其是结尾页：初始 → 点击1 → 点击2 → 换页。试验目标软件和实际教室 Windows 电脑时分别记录结果。

结构检查不会验证运行中的隐藏状态、字体渲染或动画兼容性。静态 PNG 也展示全部对象，不能用来证明播放顺序。没有目标软件实测时，说明已做结构检查、尚未实测；不要承诺所有 Office／WPS 版本兼容。

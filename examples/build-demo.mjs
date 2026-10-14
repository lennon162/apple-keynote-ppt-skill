import fs from 'node:fs/promises';
import path from 'node:path';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

// Run from a private build directory with artifact-tool available in node_modules.
const output = path.resolve(process.argv[2] ?? '.');
await fs.mkdir(output, { recursive: true });
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const gradient = { type: 'gradient', gradientKind: 'linear', angleDeg: 0,
  stops: [{ offset: 0, color: '#7197FF' }, { offset: 47000, color: '#B68BEA' },
    { offset: 100000, color: '#ED6AAB' }] };
function text(slide, name, content, x, y, w, h, size, color = '#F5F5F7', grad = false) {
  if (grad) w = Math.min(w, Math.max(...content.split('\n').map(line =>
    [...line].reduce((sum, c) => sum + (/[^\x00-\xff]/.test(c) ? 1 : 0.59), 0))) * size + 20);
  const box = slide.shapes.add({ geometry: 'textbox', name,
    position: { left: x, top: y, width: w, height: h },
    fill: 'none', line: { fill: 'none', width: 0 } });
  box.text = content;
  box.text.style = { fontSize: size, typeface: 'Microsoft YaHei', bold: grad,
    color, insets: 0, wrap: 'none', autoFit: 'none', verticalAlignment: 'top' };
  if (grad) box.text.fill = gradient;
}
function slide() { const s = deck.slides.add(); s.background.fill = '#000000'; return s; }
{
  const s = slide();
  text(s, 'eyebrow', '让讲述，有自己的节奏', 64, 113, 960, 60, 36, '#B8B8BE');
  text(s, 'title', '让重点，被看见', 58, 224, 1160, 150, 104, '#F5F5F7', true);
  text(s, 'reveal_subtitle', '一次点击，只推进一个意思', 66, 462, 1060, 70, 40);
  s.speakerNotes.text = '先停留在标题。点击1后说：一次点击，只推进一个意思。再点击换页。';
}
{
  const s = slide();
  text(s, 'title', '先给结论，再给依据', 64, 64, 1110, 100, 66, '#F5F5F7', true);
  text(s, 'reveal_number', '一个重点', 64, 248, 1130, 150, 112, '#F5F5F7', true);
  text(s, 'reveal_scope', '让文字、照片与口播保持同一顺序', 66, 497, 1110, 70, 36, '#B8B8BE');
  s.speakerNotes.text = '初始只见标题。点击1出现重点与解释，讲完后换页。';
}
{
  const s = slide();
  text(s, 'title', '最后，把主题留下', 64, 65, 1110, 100, 72, '#F5F5F7', true);
  text(s, 'peace_line', '记住劳动者，珍惜和平', 64, 238, 1130, 90, 58);
  text(s, 'caption_left', '回到一个真实的人', 66, 368, 670, 62, 36, '#B8B8BE');
  text(s, 'caption_right', '也回到我们的今天', 66, 459, 670, 62, 36, '#B8B8BE');
  text(s, 'closing_sentence', '把一个人的姓名，放回一段共同的历史', 66, 589, 1148, 62, 32, '#B3A1FF');
  s.speakerNotes.text = '点击1出现主题与第一句，点击2出现后半句与结尾句。最后停留，讲完再结束放映。';
}
await (await PresentationFile.exportPptx(deck)).save(path.join(output, 'base.pptx'));
for (let i = 0; i < deck.slides.items.length; i++) {
  const blob = await deck.export({ slide: deck.slides.items[i], format: 'png', scale: 1 });
  await fs.writeFile(path.join(output, i === 0 ? 'preview.png' : `slide-${i + 1}.png`),
    new Uint8Array(await blob.arrayBuffer()));
}
console.log(JSON.stringify({ output, slides: deck.slides.items.length }));

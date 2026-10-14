import importlib.util
import json
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path
from xml.etree import ElementTree as ET

SCRIPT = Path(__file__).parents[1] / 'apple-keynote-ppt/scripts/pptx_motion.py'
spec = importlib.util.spec_from_file_location('motion', SCRIPT)
motion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motion)

# Two real picture nodes and extension namespace exercise alias and XML preservation.
SLIDE = f'''<p:sld xmlns:p="{motion.P}" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main" mc:Ignorable="a14">
<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/></p:nvGrpSpPr>
<p:sp><p:nvSpPr><p:cNvPr id="2" name="title"/></p:nvSpPr></p:sp>
<p:sp><p:nvSpPr><p:cNvPr id="5" name="line"/></p:nvSpPr></p:sp>
<p:pic><p:nvPicPr><p:cNvPr id="9" name=""/></p:nvPicPr></p:pic>
<p:pic><p:nvPicPr><p:cNvPr id="10" name=""/></p:nvPicPr></p:pic>
</p:spTree></p:cSld><p:extLst/></p:sld>'''.encode()
GROUPS = [['line', '@picture1'], ['@picture2']]


class MotionTests(unittest.TestCase):
    def test_order_targets_and_namespaces(self):
        output = motion.patch_xml(SLIDE, GROUPS, False, 600, False)
        root = ET.fromstring(output)
        report = motion.inspect_slide(root, GROUPS)
        self.assertEqual(report['groups'], [['5', '9'], ['10']])
        self.assertIn(b'xmlns:a14=', output)
        self.assertIn(b'mc:Ignorable="a14"', output)
        self.assertEqual([x.tag.split('}')[-1] for x in root],
                         ['cSld', 'transition', 'timing', 'extLst'])
        self.assertEqual(len(root.findall('.//p:anim', motion.NS)), 3)

    def test_fade_only_and_explicit_replace(self):
        first = motion.patch_xml(SLIDE, GROUPS, False, 500, True)
        self.assertFalse(ET.fromstring(first).findall('.//p:anim', motion.NS))
        with self.assertRaisesRegex(ValueError, 'Existing animation'):
            motion.patch_xml(first, GROUPS, False, 500, True)
        second = motion.patch_xml(first, GROUPS, True, 500, True)
        self.assertEqual(motion.inspect_slide(ET.fromstring(second), GROUPS)['click_steps'], 2)

    def test_reject_unknown_duplicate_and_missing_targets(self):
        with self.assertRaises(ValueError):
            motion.patch_xml(SLIDE, [['unknown']], False, 600, False)
        with self.assertRaises(ValueError):
            motion.patch_xml(SLIDE, [['line'], ['line']], False, 600, False)
        with self.assertRaises(ValueError):
            motion.patch_xml(SLIDE.replace(b'id="10"', b'id="9"'), GROUPS, False, 600, False)
        output = motion.patch_xml(SLIDE, GROUPS, False, 600, False)
        with self.assertRaisesRegex(ValueError, 'target does not exist'):
            motion.inspect_slide(ET.fromstring(output.replace(b'spid="10"', b'spid="999"')))

    def test_atomic_package_and_unchanged_source(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source, out, steps = [folder / x for x in ['in.pptx', 'out.pptx', 'steps.json']]
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('ppt/presentation.xml', f'<p:presentation xmlns:p="{motion.P}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="256" r:id="slide1"/></p:sldIdLst></p:presentation>')
                archive.writestr('ppt/_rels/presentation.xml.rels', '<Relationships><Relationship Id="slide1" Target="slides/slide1.xml"/></Relationships>')
                archive.writestr('ppt/slides/slide1.xml', SLIDE)
                archive.writestr('ppt/notesSlides/notesSlide1.xml', b'original notes')
            before = source.read_bytes()
            steps.write_text(json.dumps({'1': GROUPS}))
            args = Namespace(command='apply', input=source, output=out, steps=steps,
                             replace=False, duration=600, fade_only=False)
            self.assertEqual(motion.process(args)['status'], 'pass')
            self.assertEqual(before, source.read_bytes())
            with zipfile.ZipFile(out) as archive:
                self.assertEqual(archive.read('ppt/notesSlides/notesSlide1.xml'), b'original notes')
            with self.assertRaisesRegex(ValueError, 'new file'):
                motion.process(args)
            steps.write_text(json.dumps({'9': GROUPS}))
            args.output = folder / 'bad.pptx'
            with self.assertRaises(ValueError):
                motion.process(args)
            self.assertFalse(args.output.exists())

    def test_use_presentation_order_after_slide_rearrangement(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'reordered.pptx'
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('ppt/presentation.xml', f'<p:presentation xmlns:p="{motion.P}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="257" r:id="second"/><p:sldId id="256" r:id="first"/></p:sldIdLst></p:presentation>')
                archive.writestr('ppt/_rels/presentation.xml.rels', '<Relationships><Relationship Id="first" Target="slides/slide1.xml"/><Relationship Id="second" Target="/ppt/slides/slide2.xml"/></Relationships>')
                archive.writestr('ppt/slides/slide1.xml', SLIDE)
                archive.writestr('ppt/slides/slide2.xml', SLIDE)
            with zipfile.ZipFile(source) as archive:
                self.assertEqual(motion.slide_parts(archive),
                                 ['ppt/slides/slide2.xml', 'ppt/slides/slide1.xml'])


if __name__ == '__main__':
    unittest.main()

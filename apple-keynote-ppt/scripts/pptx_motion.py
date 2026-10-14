#!/usr/bin/env python3
"""Apply/audit native click animations; Python 3.10+, standard library only."""
import argparse
import json
import os
import posixpath
import re
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS = {'p': P}
ET.register_namespace('p', P)


def node(parent, name, **attrs):
    return ET.SubElement(parent, '{' + P + '}' + name,
                         {key: str(value) for key, value in attrs.items()})


def read_plan(path):
    if path is None:
        return None
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Steps must be an object of slide numbers and click groups')
    result = {}
    for key, groups in data.items():
        if not re.fullmatch(r'[1-9][0-9]*', key):
            raise ValueError(f'Invalid slide number: {key}')
        if not isinstance(groups, list) or any(
            not isinstance(g, list) or not g or any(
                not isinstance(n, str) or not n for n in g) for g in groups
        ):
            raise ValueError(f'Slide {key}: each click group needs nonempty object names')
        result[int(key)] = groups
    return result


def slide_parts(package):
    presentation = ET.fromstring(package.read('ppt/presentation.xml'))
    rels = ET.fromstring(package.read('ppt/_rels/presentation.xml.rels'))
    targets = {}
    for relationship in rels:
        if relationship.get('TargetMode') == 'External':
            continue
        target = relationship.get('Target', '')
        targets[relationship.get('Id')] = posixpath.normpath(
            target.lstrip('/') if target.startswith('/') else posixpath.join('ppt', target))
    rid = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    parts = []
    for slide in presentation.findall('./p:sldIdLst/p:sldId', NS):
        part = targets.get(slide.get(rid))
        if part is None or not part.startswith('ppt/slides/') or part not in package.namelist():
            raise ValueError('Missing or invalid slide relationship')
        parts.append(part)
    if len(parts) != len(set(parts)):
        raise ValueError('Duplicate slide relationship')
    return parts


def identities(root):
    props = root.findall('.//p:cNvPr', NS)
    ids = [p.get('id') for p in props]
    duplicate = [i for i, count in Counter(ids).items() if count > 1]
    if duplicate or any(i is None or not i.isdigit() for i in ids):
        raise ValueError(f'Invalid or duplicate object IDs: {duplicate}')
    names = {}
    for p in props:
        if p.get('name'):
            names.setdefault(p.get('name'), []).append(p.get('id'))
    pictures = [p.get('id') for p in
                root.findall('./p:cSld/p:spTree/p:pic/p:nvPicPr/p:cNvPr', NS)]
    return set(ids), names, pictures


def resolve(root, groups):
    _, names, pictures = identities(root)
    resolved = []
    seen = set()
    for group in groups:
        row = []
        for name in group:
            alias = re.fullmatch(r'@picture([1-9][0-9]*)', name)
            if alias:
                index = int(alias.group(1)) - 1
                candidates = pictures[index:index + 1]
            else:
                candidates = names.get(name, [])
            if len(candidates) != 1:
                raise ValueError(f'Object must resolve exactly once: {name}')
            sid = candidates[0]
            if sid in seen:
                raise ValueError(f'Object appears in more than one animation: {name}')
            seen.add(sid)
            row.append(sid)
        resolved.append(row)
    return resolved


def inspect_slide(root, groups=None):
    ids, _, _ = identities(root)
    timing = root.find('p:timing', NS)
    actual = []
    if timing is not None:
        tids = [x.get('id') for x in timing.findall('.//p:cTn', NS)]
        if len(tids) != len(set(tids)) or None in tids:
            raise ValueError('Duplicate or missing timing IDs')
        for target in timing.findall('.//p:spTgt', NS):
            if target.get('spid') not in ids:
                raise ValueError(f'Animation target does not exist: {target.get("spid")}')
        for build in timing.findall('./p:bldLst/*', NS):
            if build.get('spid') is not None and build.get('spid') not in ids:
                raise ValueError('Build-list target does not exist')
        for effect in timing.findall('.//p:cTn', NS):
            kind = effect.get('nodeType')
            if kind not in ('clickEffect', 'withEffect', 'afterEffect'):
                continue
            targets = list(dict.fromkeys(x.get('spid') for x in
                                        effect.findall('.//p:spTgt', NS)))
            if kind == 'clickEffect':
                actual.append([])
            if targets and not actual:
                raise ValueError('Non-click effect before first click group')
            if actual:
                actual[-1].extend(targets)
    if groups is not None and actual != resolve(root, groups):
        raise ValueError(f'Click groups differ from plan: actual={actual}')
    return {'object_count': len(ids), 'click_steps': len(actual), 'groups': actual}


def make_timing(groups, pictures, duration, fade_only):
    timing = ET.Element('{' + P + '}timing')
    counter = 0

    def ctn(parent, **attrs):
        nonlocal counter
        counter += 1
        return node(parent, 'cTn', id=counter, **attrs)

    def condition(parent, delay):
        node(node(parent, 'stCondLst'), 'cond', delay=delay)

    def behavior(parent, sid, ms, **attrs):
        b = node(parent, 'cBhvr')
        c = ctn(b, dur=ms, fill='hold', **attrs)
        node(node(b, 'tgtEl'), 'spTgt', spid=sid)
        return b, c

    root = ctn(node(node(timing, 'tnLst'), 'par'), dur='indefinite',
               restart='never', nodeType='tmRoot')
    seq = node(node(root, 'childTnLst'), 'seq', concurrent=1, nextAc='seek')
    main = ctn(seq, dur='indefinite', nodeType='mainSeq')
    children = node(main, 'childTnLst')
    for group in groups:
        outer = ctn(node(children, 'par'), fill='hold')
        condition(outer, 'indefinite')
        inner = ctn(node(node(outer, 'childTnLst'), 'par'), fill='hold')
        condition(inner, 0)
        effects = node(inner, 'childTnLst')
        for index, sid in enumerate(group):
            effect = ctn(node(effects, 'par'), presetID=10, presetClass='entr',
                         presetSubtype=0, fill='hold',
                         nodeType='clickEffect' if index == 0 else 'withEffect')
            condition(effect, 0)
            child = node(effect, 'childTnLst')
            set_node = node(child, 'set')
            b, c = behavior(set_node, sid, 1)
            condition(c, 0)
            node(node(b, 'attrNameLst'), 'attrName').text = 'style.visibility'
            node(node(set_node, 'to'), 'strVal', val='visible')
            behavior(node(child, 'animEffect', transition='in', filter='fade'), sid, duration)
            if not fade_only:
                motion = node(child, 'anim', calcmode='lin', valueType='num')
                b, _ = behavior(motion, sid, duration, decel=65000)
                b.set('additive', 'base')
                node(node(b, 'attrNameLst'), 'attrName').text = 'ppt_y'
                values = node(motion, 'tavLst')
                for tm, value in [(0, '#ppt_y+0.025'), (100000, '#ppt_y')]:
                    node(node(node(values, 'tav', tm=tm), 'val'), 'strVal', val=value)
    for name, event in [('prevCondLst', 'onPrev'), ('nextCondLst', 'onNext')]:
        c = node(node(seq, name), 'cond', evt=event, delay=0)
        node(node(c, 'tgtEl'), 'sldTgt')
    builds = node(timing, 'bldLst')
    for group in groups:
        for sid in group:
            if sid not in pictures:
                node(builds, 'bldP', spid=sid, grpId=0, animBg=1)
    return timing


def patch_xml(data, groups, replace, duration, fade_only):
    root = ET.fromstring(data)
    identities(root)
    if root.find('p:timing', NS) is not None and not replace:
        raise ValueError('Existing animation; use --replace explicitly')
    resolved = resolve(root, groups)
    _, _, pictures = identities(root)
    # DOM preserves original namespace declarations, including mc:Ignorable prefixes.
    dom = minidom.parseString(data)
    slide = dom.documentElement
    for child in list(slide.childNodes):
        if child.nodeType == child.ELEMENT_NODE and child.namespaceURI == P and (
            child.localName in ('transition', 'timing')):
            slide.removeChild(child)
    transition = ET.Element('{' + P + '}transition', {'spd': 'med', 'advClick': '1'})
    node(transition, 'fade')
    additions = [transition]
    if resolved:
        additions.append(make_timing(resolved, pictures, duration, fade_only))
    extension = next((c for c in slide.childNodes if c.nodeType == c.ELEMENT_NODE
                      and c.namespaceURI == P and c.localName == 'extLst'), None)
    for addition in additions:
        subtree = minidom.parseString(ET.tostring(addition, encoding='utf-8'))
        slide.insertBefore(dom.importNode(subtree.documentElement, True), extension)
    result = dom.toxml(encoding='UTF-8')
    inspect_slide(ET.fromstring(result), groups)
    return result


def process(args):
    plan = read_plan(args.steps)
    if args.command == 'apply' and plan is None:
        raise ValueError('apply requires --steps')
    with zipfile.ZipFile(args.input) as src:
        if len(src.namelist()) != len(set(src.namelist())):
            raise ValueError('Duplicate ZIP entries')
        if src.testzip() is not None:
            raise ValueError('Corrupted ZIP member')
        parts = slide_parts(src)
        if not parts:
            raise ValueError('No slides found')
        known = set(range(1, len(parts) + 1))
        if plan is not None and set(plan) - known:
            raise ValueError('Plan refers to nonexistent slides')
        updates, report = {}, []
        for number, part in enumerate(parts, 1):
            data = src.read(part)
            if args.command == 'apply' and number in plan:
                data = patch_xml(data, plan[number], args.replace, args.duration, args.fade_only)
                updates[part] = data
            expected = plan.get(number) if plan is not None else None
            report.append({'slide': number, **inspect_slide(ET.fromstring(data), expected)})
        if args.command == 'apply':
            out = Path(args.output)
            if out.resolve() == Path(args.input).resolve() or out.exists():
                raise ValueError('Output must be a new file, distinct from input')
            out.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=out.parent, suffix='.pptx', delete=False) as f:
                    temporary = f.name
                with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as dst:
                    for entry in src.infolist():
                        dst.writestr(entry, updates.get(entry.filename, src.read(entry.filename)))
                os.replace(temporary, out)
            finally:
                if temporary is not None and os.path.exists(temporary):
                    os.unlink(temporary)
    return {'status': 'pass', 'scope': 'OOXML structure only; native playback not verified',
            'slides': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    audit = sub.add_parser('audit')
    audit.add_argument('input')
    audit.add_argument('--steps')
    apply = sub.add_parser('apply')
    apply.add_argument('input')
    apply.add_argument('output')
    apply.add_argument('--steps', required=True)
    apply.add_argument('--replace', action='store_true')
    apply.add_argument('--fade-only', action='store_true')
    apply.add_argument('--duration', type=int, default=600)
    args = parser.parse_args()
    if args.command == 'apply' and not 100 <= args.duration <= 3000:
        parser.error('--duration must be between 100 and 3000 ms')
    try:
        print(json.dumps(process(args), ensure_ascii=False, indent=2))
    except (ValueError, OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()

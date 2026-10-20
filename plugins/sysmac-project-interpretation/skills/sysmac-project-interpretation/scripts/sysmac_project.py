#!/usr/bin/env python3
"""Read-only evidence extraction for observed Sysmac .smc2 archives (stdlib only)."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import xml.etree.ElementTree as ET
import zipfile

CODE_TYPES = {
    'Variables', 'DataType', 'NexTask', 'Program', 'Function', 'FunctionBlock',
    'Pou', 'PouBody', 'PouBodySourceHolder',
}
HMI_TYPES = {
    'HmiPage', 'LocalisationResources', 'AlarmGroup', 'CodeEditorModel',
    'VariableMapping', 'DeviceReference',
}
SUFFIXES = {'.xml', '.dat', '.vb', '.xaml', '.json', '.txt', '.st', '.slwd'}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _hash_stream(stream)


def _hash_stream(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()


def local(tag):
    return tag.rsplit('}', 1)[-1]


def xml_root(data):
    # No DTD is needed for the observed project XML, including UTF-16 inputs.
    probe = data.replace(b'\x00', b'') if isinstance(data, bytes) else data
    marker = b'<!DOCTYPE' if isinstance(probe, bytes) else '<!DOCTYPE'
    entity = b'<!ENTITY' if isinstance(probe, bytes) else '<!ENTITY'
    if marker in probe.upper() or entity in probe.upper():
        raise ValueError('DTD/entity declarations are unsupported')
    return ET.fromstring(data)


def graph_entities(root):
    result = []

    def walk(node, parent, inherited_hmi=False):
        attrs = dict(node.attrib)
        name = attrs.get('name') or attrs.get('type') or '(unnamed)'
        path = f'{parent}/{name}' if parent else name
        kind = attrs.get('type', '')
        is_na_device = kind == 'Device' and attrs.get('subtype', '').upper().startswith('NA')
        hmi = inherited_hmi or is_na_device or kind.lower().startswith(('hmi', 'na')) or kind in HMI_TYPES
        result.append({
            'path': path, 'parent_path': parent, 'id': attrs.get('id', ''),
            'type': kind, 'subtype': attrs.get('subtype', ''),
            'attributes': attrs, 'hmi_context': hmi,
        })
        for holder in node:
            if local(holder.tag) == 'ChildEntities':
                for child in holder:
                    if local(child.tag) == 'Entity':
                        walk(child, path, hmi)

    if local(root.tag) == 'Entity':
        walk(root, '')
    else:
        for node in root:
            if local(node.tag) == 'Entity':
                walk(node, '')
    return result


def decode_text(data):
    encodings = ['utf-8-sig']
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        encodings = ['utf-16']
    elif data[:100].count(b'\x00') > 10:
        encodings = ['utf-16-le', 'utf-16-be']
    for encoding in encodings:
        try:
            text = data.decode(encoding)
            if any(ord(c) < 32 and c not in '\t\r\n' for c in text):
                continue
            return text, encoding
        except UnicodeError:
            pass
    return None, None


def parse_payload(entity, text):
    parsed = {}
    errors = []
    if entity['type'] == 'PouBody' and entity['subtype'] == 'Ladder':
        rungs = []
        index = 0
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rung = json.loads(line)
                if not isinstance(rung, dict) or not isinstance(rung.get('CLs'), list):
                    raise ValueError('expected rung object with CLs list')
                rungs.append({'index': index, 'source_line': line_number, 'data': rung})
            except (ValueError, TypeError) as exc:
                errors.append({'rung_index': index, 'source_line': line_number, 'error': str(exc)})
            index += 1
        parsed.update(rungs=rungs, rung_records=index)
        if not index:
            errors.append({'error': 'empty ladder payload'})
    elif entity['type'] == 'Variables' and text.lstrip().startswith('[SLWD'):
        parsed['declarations'] = [
            {'source_line': n, 'fields': dict(part.split('=', 1) for part in line[2:].split('\t') if '=' in part)}
            for n, line in enumerate(text.splitlines(), 1) if line.startswith('++')
        ]
    elif entity['type'] == 'NexTask':
        try:
            root = xml_root(text)
            parsed['task_assignments'] = [dict(n.attrib) for n in root.iter() if local(n.tag) == 'AssociatedProgramData']
            parsed['task_settings'] = [dict(n.attrib) for n in root.iter() if local(n.tag) == 'GeneralSettingsData']
        except (ET.ParseError, ValueError) as exc:
            errors.append({'error': f'task XML: {exc}'})
    if entity['type'] == 'PouBody' and entity['subtype'] == 'StructuredText':
        parsed['st_status'] = 'wrapped-st-review-required' if text.lstrip().startswith('<') else 'plain-text-review-required'
    if errors:
        parsed['parse_errors'] = errors
    return parsed


def readable(entity, payload, text):
    lines = [f"ENTITY: {entity['path']}", f"ENTITY ID: {entity['id']}",
             f"ARCHIVE: {payload['archive_member']}", f"PAYLOAD SHA256: {payload['sha256']}", '']
    if 'rungs' in payload:
        lines.append('Full geometry preserved. This view is not a synthesized execution listing.')
        for rung in payload['rungs']:
            lines.append(f"===== RUNG {rung['index']} (zero-based archive order), payload line {rung['source_line']} =====")
            lines.append(json.dumps(rung['data'], indent=2, ensure_ascii=False))
            for cell in rung['data']['CLs']:
                if isinstance(cell, dict) and isinstance(cell.get('TXT'), str):
                    lines.extend(['INLINE TXT (verbatim content):', cell['TXT']])
        if payload.get('parse_errors'):
            lines.append('INCOMPLETE LADDER: ' + json.dumps(payload['parse_errors']))
    else:
        lines.append(text)
    return '\n'.join(lines) + '\n'


def decode(source, out, *, oem=None, device=None, hmi=False, max_member_mb=64, max_total_mb=1024):
    source, out = Path(source).resolve(), Path(out).resolve()
    if not source.is_file():
        raise ValueError(f'Source file does not exist: {source}')
    if out.suffix.lower() == '.smc2' or out == source:
        raise ValueError('Output must be a decode directory, not a project archive')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError('Output must be absent or empty; choose a new review directory')
    if max_member_mb <= 0 or max_total_mb <= 0:
        raise ValueError('Extraction limits must be positive')
    before = sha256(source)
    warnings = []
    total = 0
    member_limit, total_limit = int(max_member_mb * 1024**2), int(max_total_mb * 1024**2)
    with zipfile.ZipFile(source, 'r') as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if len({m.filename for m in members}) != len(members):
            raise ValueError('Duplicate archive member names are ambiguous')
        candidates = [m for m in members if PurePosixPath(m.filename).suffix.lower() == '.oem']
        if oem:
            candidates = [m for m in candidates if m.filename == oem]
        if len(candidates) != 1:
            raise ValueError('Select exactly one OEM member with --oem; candidates: ' + ', '.join(m.filename for m in candidates))
        graph_member = candidates[0]
        if graph_member.file_size > member_limit:
            raise ValueError('OEM member exceeds --max-member-mb')
        entities = graph_entities(xml_root(archive.read(graph_member)))
        if not entities:
            raise ValueError('OEM contains no supported Entity graph')
        if device and device not in {e['path'] for e in entities}:
            raise ValueError('--device must match an exact entity path in the graph')
        counts = Counter(e['path'] for e in entities)
        for path, count in counts.items():
            if count > 1:
                warnings.append(f'Duplicate entity path ({count}): {path}')
        index = defaultdict(list)
        for member in members:
            index[PurePosixPath(member.filename).stem.casefold()].append(member)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'raw').mkdir(exist_ok=True)
        (out / 'readable').mkdir(exist_ok=True)
        for ordinal, entity in enumerate(entities):
            matches = index.get(entity['id'].casefold(), []) if entity['id'] else []
            entity['files'] = [m.filename for m in matches]
            entity['payloads'] = []
            in_device = not device or entity['path'] == device or entity['path'].startswith(device + '/')
            selected = in_device and (entity['type'] in CODE_TYPES and not entity['hmi_context'] or hmi and entity['hmi_context'])
            entity['extraction_status'] = 'selected' if selected else 'not-selected'
            if not selected:
                continue
            payload_members = [m for m in matches if PurePosixPath(m.filename).suffix.lower() in SUFFIXES]
            if not payload_members:
                # POU/group entities normally own child bodies, not their own payload.
                container = entity['type'] in {'Program', 'Function', 'FunctionBlock', 'Pou'} or any(
                    child['parent_path'] == entity['path'] for child in entities
                )
                entity['extraction_status'] = 'container-no-payload' if container else 'no-supported-payload'
                if not container:
                    warnings.append(f"No supported payload: {entity['path']}")
            suffixes = Counter(PurePosixPath(m.filename).suffix.lower() for m in payload_members)
            if any(n > 1 for n in suffixes.values()):
                warnings.append(f"Multiple payload candidates with same extension: {entity['path']}")
            for member in payload_members:
                payload = {'archive_member': member.filename, 'size': member.file_size}
                entity['payloads'].append(payload)
                if member.file_size > member_limit or total + member.file_size > total_limit:
                    payload['status'] = 'skipped-limit'
                    warnings.append(f'Extraction limit: {member.filename}')
                    continue
                data = archive.read(member)
                total += len(data)
                payload['sha256'] = hashlib.sha256(data).hexdigest()
                token = f"{ordinal:05d}_" + hashlib.sha256(member.filename.encode('utf-8')).hexdigest()[:16]
                raw_path = 'raw/' + token + PurePosixPath(member.filename).suffix.lower()
                (out / raw_path).write_bytes(data)
                payload['raw'] = raw_path
                text, encoding = decode_text(data)
                if text is None:
                    payload['status'] = 'binary-or-unsupported-encoding'
                    warnings.append(f'Unreadable text: {member.filename}')
                    continue
                payload.update(status='decoded-text', encoding=encoding)
                payload.update(parse_payload(entity, text))
                if payload.get('parse_errors'):
                    payload['status'] = 'partial-parse'
                    warnings.append(f'Payload parse errors: {member.filename}')
                if payload.get('st_status') == 'wrapped-st-review-required':
                    warnings.append(f'Wrapped ST requires content/protection inspection: {member.filename}')
                payload['readable'] = 'readable/' + token + '.txt'
                (out / payload['readable']).write_text(readable(entity, payload, text), encoding='utf-8')
    after = sha256(source)
    if after != before:
        raise ValueError('Source changed during decode; discard this decode and retry with a stable source copy')
    assignments = [
        {'task_path': e['path'], 'archive_member': p['archive_member'], **a}
        for e in entities for p in e['payloads'] for a in p.get('task_assignments', [])
    ]
    program_names = {a.get('ProgramName', '').casefold() for a in assignments}
    inventory = {
        'schema_version': 1, 'source_sha256': before, 'entities': len(entities),
        'types': dict(sorted(Counter(e['type'] for e in entities).items())),
        'payload_statuses': dict(Counter(p['status'] for e in entities for p in e['payloads'])),
        'ladder_bodies_with_decoded_rungs': sum(any('rungs' in p for p in e['payloads']) for e in entities),
        'decoded_rungs': sum(len(p.get('rungs', [])) for e in entities for p in e['payloads']),
        'task_assignments': assignments,
        'programs_without_matching_extracted_assignment': [
            e['path'] for e in entities if e['type'] == 'Program' and e['attributes'].get('name', '').casefold() not in program_names
        ],
        'assignment_note': 'Name-based candidates only; inspect device scope, extraction gaps and task conditions.',
    }
    manifest = {
        'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'source': str(source), 'source_sha256': before, 'source_sha256_after': after,
        'source_unchanged': True, 'oem_member': graph_member.filename,
        'options': {'device': device, 'hmi': hmi, 'max_member_mb': max_member_mb, 'max_total_mb': max_total_mb},
        'extracted_bytes': total, 'warnings': warnings,
        'validation': 'Archive/source extraction only; no native compile, simulation or hardware operation.',
    }
    write_json(out / 'entities.json', entities)
    write_json(out / 'inventory.json', inventory)
    write_json(out / 'manifest.json', manifest)
    return {'output': str(out), **inventory, 'warnings': len(warnings)}


def load_snapshot(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    entities = json.loads((directory / 'entities.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or manifest.get('source_unchanged') is not True:
        raise ValueError('Unsupported or unverified snapshot manifest')
    return directory, manifest, entities


def snapshot_file(directory, relative):
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory):
        raise ValueError('Snapshot file points outside the decode directory')
    return path


def verified_text(directory, payload):
    path = snapshot_file(directory, payload['raw'])
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != payload['sha256']:
        raise ValueError(f'Decoded raw file hash mismatch: {path}')
    return data.decode(payload['encoding'])


def find(directory, needle, limit=50):
    if limit < 1 or not needle:
        raise ValueError('Search requires nonempty text and a positive limit')
    directory, manifest, entities = load_snapshot(directory)
    hits = []
    total = 0
    for entity in entities:
        for payload in entity['payloads']:
            if 'encoding' not in payload:
                continue
            for line_number, line in enumerate(verified_text(directory, payload).splitlines(), 1):
                if needle.casefold() in line.casefold():
                    total += 1
                    if len(hits) < limit:
                        hits.append({'entity_path': entity['path'], 'archive_member': payload['archive_member'],
                                     'source_line': line_number, 'text': line, 'readable': payload.get('readable')})
    return {'source_sha256': manifest['source_sha256'], 'query': needle, 'total_matching_lines': total,
            'returned': len(hits), 'hits': hits, 'coverage_warnings': manifest['warnings']}


def signatures(directory, entity):
    result = []
    unknown = entity['extraction_status'] != 'selected'
    for payload in entity['payloads']:
        if 'encoding' not in payload or payload.get('parse_errors'):
            unknown = True
        if 'encoding' in payload:
            text = verified_text(directory, payload).replace('\r\n', '\n').replace('\r', '\n')
            if 'rungs' in payload and not payload.get('parse_errors'):
                # Reparse verified raw evidence: the derived JSON may have been edited.
                data = [r['data'] for r in parse_payload(entity, text)['rungs']]
            else:
                data = text
            result.append((PurePosixPath(payload['archive_member']).suffix.lower(), data))
        else:
            result.append((PurePosixPath(payload['archive_member']).suffix.lower(), payload.get('sha256')))
    return sorted(result, key=lambda x: json.dumps(x, sort_keys=True)), unknown


def compare(old_directory, new_directory, mappings=None):
    old_dir, old_manifest, old_entities = load_snapshot(old_directory)
    new_dir, new_manifest, new_entities = load_snapshot(new_directory)
    mappings = mappings or {}
    if not isinstance(mappings, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in mappings.items()):
        raise ValueError('Rename map must be an object of old path to new path strings')

    def keyed(entities):
        result = {}
        for entity in entities:
            if entity['extraction_status'] == 'not-selected':
                continue
            if entity['path'] in result:
                raise ValueError('Duplicate entity path requires manual comparison: ' + entity['path'])
            result[entity['path']] = entity
        return result

    old, new = keyed(old_entities), keyed(new_entities)
    if set(mappings) - set(old) or set(mappings.values()) - set(new):
        raise ValueError('Rename map refers to an entity outside the selected snapshots')
    translated = [mappings.get(key, key) for key in old]
    if len(set(translated)) != len(translated):
        raise ValueError('Rename map creates an ambiguous many-to-one match')
    changes, matched_new = [], set()
    for key, entity in old.items():
        target = mappings.get(key, key)
        if target not in new:
            changes.append({'status': 'removed', 'old_path': key})
            continue
        matched_new.add(target)
        left, left_unknown = signatures(old_dir, entity)
        right, right_unknown = signatures(new_dir, new[target])
        same = left == right and (entity['type'], entity['subtype']) == (new[target]['type'], new[target]['subtype'])
        status = 'unchanged-extracted-content' if same else 'changed-extracted-content'
        if left_unknown or right_unknown:
            status = 'incomplete-or-unknown' if same else 'changed-with-incomplete-coverage'
        changes.append({'status': status, 'old_path': key, 'new_path': target,
                        'old_members': [p['archive_member'] for p in entity['payloads']],
                        'new_members': [p['archive_member'] for p in new[target]['payloads']]})
    changes.extend({'status': 'added', 'new_path': key} for key in new if key not in matched_new)
    return {'schema_version': 1, 'old_source_sha256': old_manifest['source_sha256'],
            'new_source_sha256': new_manifest['source_sha256'], 'rename_map': mappings,
            'comparison': 'Structural ladder / normalized text of selected extracted content; not semantic equivalence.',
            'old_options': old_manifest['options'], 'new_options': new_manifest['options'],
            'old_warnings': old_manifest['warnings'], 'new_warnings': new_manifest['warnings'],
            'counts': dict(Counter(c['status'] for c in changes)), 'entities': changes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    dec = sub.add_parser('decode', help='Extract read-only source evidence into a fresh directory')
    dec.add_argument('source', type=Path)
    dec.add_argument('--out', type=Path, required=True)
    dec.add_argument('--oem')
    dec.add_argument('--device')
    dec.add_argument('--hmi', action='store_true')
    dec.add_argument('--max-member-mb', type=float, default=64)
    dec.add_argument('--max-total-mb', type=float, default=1024)
    search = sub.add_parser('find', help='Find literal text in extracted payloads')
    search.add_argument('directory', type=Path)
    search.add_argument('text')
    search.add_argument('--limit', type=int, default=50)
    diff = sub.add_parser('compare', help='Compare extracted snapshots without discarding ladder geometry')
    diff.add_argument('old_directory', type=Path)
    diff.add_argument('new_directory', type=Path)
    diff.add_argument('--map', type=Path)
    diff.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'decode':
            result = decode(args.source, args.out, oem=args.oem, device=args.device, hmi=args.hmi,
                            max_member_mb=args.max_member_mb, max_total_mb=args.max_total_mb)
        elif args.command == 'find':
            result = find(args.directory, args.text, args.limit)
        else:
            mappings = json.loads(args.map.read_text(encoding='utf-8')) if args.map else None
            result = compare(args.old_directory, args.new_directory, mappings)
            if args.out:
                target = args.out.resolve()
                if target.exists() or target.suffix.lower() == '.smc2':
                    raise ValueError('Comparison output must be a new JSON file')
                if target.suffix.lower() != '.json':
                    raise ValueError('Comparison output must have a .json extension')
                for directory in (args.old_directory.resolve(), args.new_directory.resolve()):
                    if target.is_relative_to(directory):
                        raise ValueError('Write comparison outside the input snapshot directories')
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('x', encoding='utf-8') as stream:
                    json.dump(result, stream, indent=2, ensure_ascii=False)
                    stream.write('\n')
                result = {'output': str(target), 'counts': result['counts']}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

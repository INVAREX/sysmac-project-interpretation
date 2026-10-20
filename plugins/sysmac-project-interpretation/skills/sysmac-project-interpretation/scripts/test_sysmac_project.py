"""Behavioral tests for extraction fidelity and evidence limits. Run with unittest."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import sysmac_project as sp


RUNG = {
    'CMT': 'branch example', 'VLs': [{'X': 2, 'Y': 1}],
    'CLs': [
        {'__type': 'LD', 'Var': 'Mode.Auto', 'X': 0, 'Dwn': True},
        {'__type': 'ST', 'Var': 'Seq.Step_1', 'S': True, 'X': 3, 'Y': 1},
        {'__type': 'F', 'Name': 'Inline', 'X': 2, 'TXT': 'Counter := Counter + 1;\r\nDone := TRUE;',
         'In': [{'Arg': 'InOut', 'Var': 'Counter', 'IO': True, 'Type': 'INT'}]},
    ],
}
OEM = '''<Root><Entity id="solution" name="Different_Project" type="Solution">
<ChildEntities><Entity id="plc" name="NX_Controller" type="Controller"><ChildEntities>
<Entity id="main" name="Main" type="Program"><ChildEntities>
<Entity id="ladder" name="Sequence" type="PouBody" subtype="Ladder"/>
<Entity id="variables" name="Variables" type="Variables"/>
<Entity id="protected" name="Hidden" type="PouBody" subtype="StructuredText"/>
</ChildEntities></Entity>
<Entity id="unscheduled" name="Unused" type="Program"/>
<Entity id="task" name="PrimaryTask" type="NexTask"/>
</ChildEntities></Entity>
<Entity id="hmi" name="Screen" type="Device" subtype="NA"><ChildEntities>
<Entity id="page" name="Home" type="HmiPage"/>
<Entity id="hmi-vars" name="Variables" type="Variables"/>
</ChildEntities></Entity></ChildEntities></Entity></Root>'''


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, name='project', rung=None, extra=None, ladder_text=None, oem=OEM):
        path = self.base / (name + '.smc2')
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('solution.oem', oem)
            z.writestr('project/ladder.xml', ladder_text if ladder_text is not None else json.dumps(rung or RUNG))
            z.writestr('project/variables.xml', '[SLWD version=1.0]\n++N=Counter\tD=INT\tR=1\n')
            z.writestr('project/protected.xml', '<StructuredTextModel><Encrypted>abc</Encrypted></StructuredTextModel>')
            z.writestr('project/task.xml', '<data><Programs><AssociatedProgramData ProgramName="Main" SequenceNumber="1"/></Programs></data>')
            z.writestr('project/page.dat', '{"Text":"HMI only"}')
            z.writestr('project/hmi-vars.xml', '<Variables><Variable Name="Operator_Input" Address="NX_Controller.Counter"/></Variables>')
            for member, data in (extra or {}).items():
                z.writestr(member, data)
        return path

    def snapshot(self, source, name='decoded', **kwargs):
        out = self.base / name
        sp.decode(source, out, **kwargs)
        _, manifest, entities = sp.load_snapshot(out)
        return out, manifest, entities

    def test_preserves_geometry_inline_st_declarations_and_source(self):
        source = self.archive()
        before = source.read_bytes()
        out, manifest, entities = self.snapshot(source)
        ladder = next(e for e in entities if e['id'] == 'ladder')['payloads'][0]
        self.assertEqual(ladder['rungs'][0]['data'], RUNG)
        self.assertEqual(ladder['rungs'][0]['index'], 0)
        self.assertEqual((out / ladder['raw']).read_bytes(), json.dumps(RUNG).encode())
        self.assertIn('Counter := Counter + 1;', (out / ladder['readable']).read_text())
        variables = next(e for e in entities if e['id'] == 'variables')['payloads'][0]
        self.assertEqual(variables['declarations'][0]['fields'], {'N': 'Counter', 'D': 'INT', 'R': '1'})
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(manifest['source_sha256'], sp.sha256(source))
        inventory = json.loads((out / 'inventory.json').read_text())
        self.assertEqual(inventory['task_assignments'][0]['ProgramName'], 'Main')
        self.assertEqual(inventory['programs_without_matching_extracted_assignment'], ['Different_Project/NX_Controller/Unused'])

    def test_hmi_opt_in_and_device_filter(self):
        source = self.archive()
        _, _, plain = self.snapshot(source)
        self.assertEqual(next(e for e in plain if e['id'] == 'page')['payloads'], [])
        self.assertEqual(next(e for e in plain if e['id'] == 'hmi-vars')['payloads'], [])
        _, _, hmi = self.snapshot(source, 'hmi', hmi=True, device='Different_Project/Screen')
        self.assertTrue(next(e for e in hmi if e['id'] == 'page')['payloads'])
        self.assertTrue(next(e for e in hmi if e['id'] == 'hmi-vars')['payloads'])
        self.assertEqual(next(e for e in hmi if e['id'] == 'ladder')['payloads'], [])

    def test_partial_ladder_keeps_index_and_reports_gap(self):
        text = json.dumps(RUNG) + '\nmalformed\n\n' + json.dumps({'CLs': [], 'CMT': 'comment rung'})
        _, manifest, entities = self.snapshot(self.archive(ladder_text=text))
        p = next(e for e in entities if e['id'] == 'ladder')['payloads'][0]
        self.assertEqual(p['status'], 'partial-parse')
        self.assertEqual([r['index'] for r in p['rungs']], [0, 2])
        self.assertEqual(p['parse_errors'][0]['source_line'], 2)
        self.assertTrue(any('parse errors' in w for w in manifest['warnings']))

    def test_wrapped_st_is_explicitly_unknown(self):
        _, manifest, entities = self.snapshot(self.archive())
        p = next(e for e in entities if e['id'] == 'protected')['payloads'][0]
        self.assertEqual(p['st_status'], 'wrapped-st-review-required')
        self.assertTrue(any('Wrapped ST' in w for w in manifest['warnings']))

    def test_refuses_reusing_output_and_ambiguous_oem(self):
        source = self.archive(extra={'second.oem': OEM})
        with self.assertRaisesRegex(ValueError, 'exactly one OEM'):
            sp.decode(source, self.base / 'bad')
        out, _, _ = self.snapshot(source, oem='solution.oem')
        with self.assertRaisesRegex(ValueError, 'absent or empty'):
            sp.decode(source, out, oem='solution.oem')

    def test_no_archive_path_traversal_or_sanitized_name_collision(self):
        # Both payloads share an entity ID. Both are retained, visibly ambiguous.
        source = self.archive(extra={'../../elsewhere/ladder.xml': json.dumps(RUNG)})
        out, manifest, entities = self.snapshot(source)
        payloads = next(e for e in entities if e['id'] == 'ladder')['payloads']
        self.assertEqual(len(payloads), 2)
        self.assertNotEqual(payloads[0]['raw'], payloads[1]['raw'])
        self.assertTrue(all((out / p['raw']).resolve().is_relative_to(out) for p in payloads))
        self.assertFalse((self.base / 'elsewhere').exists())
        self.assertTrue(any('Multiple payload candidates' in w for w in manifest['warnings']))

    def test_literal_search_and_tamper_detection(self):
        out, _, entities = self.snapshot(self.archive())
        self.assertEqual(sp.find(out, 'Seq.Step_1')['returned'], 1)
        self.assertEqual(sp.find(out, 'Seq.Step_[')['returned'], 0)
        p = next(e for e in entities if e['id'] == 'ladder')['payloads'][0]
        (out / p['raw']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            sp.find(out, 'anything')

    def test_comparison_detects_branch_edge_and_pin_type_changes(self):
        original, _, _ = self.snapshot(self.archive('old'))
        for n, mutate in enumerate([
            lambda r: r['VLs'][0].update(X=4),
            lambda r: r['CLs'][0].update(Dwn=False),
            lambda r: r['CLs'][2]['In'][0].update(Type='DINT'),
        ]):
            rung = copy.deepcopy(RUNG)
            mutate(rung)
            updated, _, _ = self.snapshot(self.archive(f'new{n}', rung=rung), f'new{n}')
            changes = sp.compare(original, updated)['entities']
            self.assertEqual(next(c for c in changes if c.get('old_path', '').endswith('/Sequence'))['status'], 'changed-extracted-content')

    def test_explicit_rename_map_and_ambiguity(self):
        old, _, _ = self.snapshot(self.archive('old'))
        new_oem = OEM.replace('name="Sequence"', 'name="Renamed"')
        new, _, _ = self.snapshot(self.archive('new', oem=new_oem), 'new')
        before = 'Different_Project/NX_Controller/Main/Sequence'
        after = 'Different_Project/NX_Controller/Main/Renamed'
        changes = sp.compare(old, new, {before: after})['entities']
        self.assertEqual(next(c for c in changes if c.get('old_path') == before)['status'], 'unchanged-extracted-content')
        with self.assertRaisesRegex(ValueError, 'many-to-one'):
            sp.compare(old, new, {before: after, 'Different_Project/NX_Controller/Main/Variables': after})

    def test_limits_and_binary_are_coverage_gaps(self):
        source = self.archive(extra={'project/main.dat': b'\x00\x01\x02\x03'})
        out, _, entities = self.snapshot(source)
        self.assertEqual(next(e for e in entities if e['id'] == 'main')['payloads'][0]['status'], 'binary-or-unsupported-encoding')
        with self.assertRaisesRegex(ValueError, 'OEM member exceeds'):
            sp.decode(source, self.base / 'tiny', max_member_mb=0.00001)
        _, manifest, limited = self.snapshot(source, 'limited', max_total_mb=0.00001)
        self.assertTrue(any(p['status'] == 'skipped-limit' for e in limited for p in e['payloads']))
        self.assertTrue(any('Extraction limit' in w for w in manifest['warnings']))
        self.assertIn('incomplete-or-unknown', sp.compare(out, self.base / 'limited')['counts'])

    def test_utf16_and_namespace_graph(self):
        source = self.archive(oem=OEM.replace('<Root>', '<Root xmlns="urn:test">'))
        with zipfile.ZipFile(source, 'a') as z:
            z.writestr('project/unscheduled.dat', 'Plain UTF-16 ST text'.encode('utf-16'))
        _, _, entities = self.snapshot(source)
        p = next(e for e in entities if e['id'] == 'unscheduled')['payloads'][0]
        self.assertEqual(p['encoding'], 'utf-16')

    def test_dtd_and_external_snapshot_paths_refused(self):
        with self.assertRaisesRegex(ValueError, 'DTD'):
            sp.xml_root('<!DOCTYPE a [<!ENTITY b "value">]><a/>')
        with self.assertRaisesRegex(ValueError, 'outside'):
            sp.snapshot_file(self.base, '../escape')


if __name__ == '__main__':
    unittest.main()

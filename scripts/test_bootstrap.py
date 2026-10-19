"""Offline security/lifecycle checks. No real token, GCP call or resource creation."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location('codespace_bootstrap', Path(__file__).resolve().parents[1] / 'infra/bootstrap/bootstrap.py')
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)
INPUTS = {'project_id': 'website-devcirrus', 'org_id': '123456789', 'billing_account': '000000-000000-000000',
          'bootstrap_state_bucket': 'devcirrus-test-bootstrap', 'site_state_bucket': 'devcirrus-test-site'}
STATE = {'lineage': 'offline-test-lineage', 'serial': 7}


class CodespaceBootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / 'private'
        self.work.mkdir(mode=0o700)
        (self.work / 'root').mkdir(mode=0o700)
        for name in b.source_files():
            shutil.copyfile(b.SOURCE / name, self.work / 'root' / name)
        b.write_json(self.work / 'inputs.tfvars.json', INPUTS)
        b.write_json(self.work / 'workspace.json', {'format': 1, 'source_sha': 'a' * 40, 'stage': 'remote'})
        (self.work / 'root/backend.tf').write_text(b.backend(INPUTS['bootstrap_state_bucket']))
        self.revision = patch.object(b, 'revision', return_value='a' * 40)
        self.revision.start()
        self.addCleanup(self.revision.stop)
        self.runner = b.Bootstrap(self.work, {'GOOGLE_OAUTH_ACCESS_TOKEN': 'FAKE-SHORT-TOKEN'}, Path('/dev/shm/fake-token'))

    def test_private_paths_reject_git_symlink_parent_traversal_and_open_permissions(self):
        with self.assertRaises(RuntimeError):
            b.private_path(b.REPO / 'private')
        with self.assertRaises(RuntimeError):
            b.private_path(self.work / '..' / 'elsewhere')
        link = Path(self.tmp.name) / 'link'
        link.symlink_to(self.work, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            b.private_path(link / 'child')
        self.work.chmod(0o755)
        with self.assertRaises(RuntimeError):
            b.private_path(self.work)

    def test_short_token_is_only_in_tmpfs_and_child_environment(self):
        with patch.dict(os.environ, {'GOOGLE_APPLICATION_CREDENTIALS': '/unwanted.json', 'TF_WORKSPACE': 'other', 'TF_CLI_ARGS_apply': '-auto-approve'}):
            with b.credentials('FAKE-SHORT-TOKEN') as (env, path):
                self.assertTrue(str(path).startswith('/dev/shm/'))
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.read_text(), 'FAKE-SHORT-TOKEN')
                self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS', env)
                self.assertNotIn('TF_WORKSPACE', env)
                self.assertNotIn('TF_CLI_ARGS_apply', env)
                self.assertEqual(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], '/unwanted.json')
            self.assertFalse(path.exists())
            self.assertNotIn('GOOGLE_OAUTH_ACCESS_TOKEN', env)

    def test_changed_saved_plan_never_applies(self):
        plan = self.work / 'bootstrap.tfplan'
        plan.write_bytes(b'approved-plan')
        approved = b.sha(plan)
        self.runner.meta.update(plan_sha256=approved, inputs_sha256=b.sha(self.work / 'inputs.tfvars.json'))
        plan.write_bytes(b'replaced-plan')
        with patch.object(self.runner, 'tf') as tf:
            with self.assertRaises(RuntimeError):
                self.runner.apply(approved)
            tf.assert_not_called()

    def test_existing_remote_state_never_overwritten_by_migration(self):
        self.runner.meta['stage'] = 'applied'
        (self.work / 'root/backend.tf').unlink()
        with patch.object(self.runner, 'private_bucket'), patch.object(self.runner, 'object', return_value={'generation': '1'}), patch.object(self.runner, 'tf') as tf:
            with self.assertRaises(RuntimeError):
                self.runner.migrate()
            tf.assert_not_called()
            self.assertFalse((self.work / 'root/backend.tf').exists())

    def test_recovery_rejects_traversal_and_unexpected_files(self):
        archive = self.work / 'unsafe.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('../escape', 'not a Terraform snapshot')
        with self.assertRaises(RuntimeError):
            b.unpack(archive, self.work / 'extract')
        self.assertFalse((self.work.parent / 'escape').exists())

    def verify_with_fake_cloud(self, plan_exit):
        objects = {}
        def cloud(*args):
            source, destination = args[2:]
            if source.startswith('gs://'):
                Path(destination).write_bytes(objects['archive'])
            else:
                objects['archive'] = Path(source).read_bytes()
            return 0, b''
        def obj(name, media=False):
            return json.dumps(STATE).encode() if media else {'generation': '12345'}
        def tf(_runner, *args, **kwargs):
            if args[:2] == ('state', 'pull'):
                return 0, json.dumps(STATE).encode()
            return (plan_exit if args[0] == 'plan' else 0), b'offline output'
        with patch.object(b.Bootstrap, 'private_bucket'), patch.object(self.runner, 'object', side_effect=obj), patch.object(self.runner, 'cloud', side_effect=cloud), patch.object(b.Bootstrap, 'tf', new=tf), patch('builtins.print'):
            self.runner.verify()
        return objects

    def test_recovery_must_read_remote_generation_and_plan_without_changes(self):
        objects = self.verify_with_fake_cloud(0)
        meta = json.loads((self.work / 'workspace.json').read_text())
        self.assertEqual(meta['stage'], 'verified')
        self.assertEqual(meta['verified']['state'], STATE)
        self.assertEqual(meta['verified']['recovery_generation'], '12345')
        self.assertNotIn(b'FAKE-SHORT-TOKEN', objects['archive'])
        with zipfile.ZipFile(self.work / 'recovery.zip') as archive:
            self.assertFalse(any('tfstate' in p or 'tfplan' in p or 'credentials' in p for p in archive.namelist()))

    def test_recovery_drift_prevents_safe_to_delete_marker(self):
        with self.assertRaises(RuntimeError):
            self.verify_with_fake_cloud(2)
        meta = json.loads((self.work / 'workspace.json').read_text())
        self.assertNotIn('verified', meta)
        self.assertNotEqual(meta['stage'], 'verified')

    def test_subprocess_output_never_writes_the_token_to_logs(self):
        output = subprocess.CompletedProcess(['fake-cli'], 0, b'error mentioning FAKE-SHORT-TOKEN')
        with patch.object(b.subprocess, 'run', return_value=output):
            _, data = self.runner.run(['fake-cli'])
        self.assertNotIn(b'FAKE-SHORT-TOKEN', data)
        self.assertNotIn(b'FAKE-SHORT-TOKEN', (self.work / 'operations.log').read_bytes())

    def test_failed_reverification_invalidates_previous_delete_marker(self):
        self.runner.meta.update(stage='verified', verified={'old': True})
        with self.assertRaises(RuntimeError):
            self.verify_with_fake_cloud(2)
        meta = json.loads((self.work / 'workspace.json').read_text())
        self.assertNotIn('verified', meta)
        self.assertEqual(meta['stage'], 'remote')

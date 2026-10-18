"""Keep full Terraform output private. Never upload plans to Actions artifacts.

Generation and digest anchors come from the plan job's immutable outputs; the
manifest is additional evidence, never an authority for expected values.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(value, pattern):
    assert re.fullmatch(pattern, value), 'Invalid identifier or immutable anchor'
    return value


def verify_file(path, expected):
    checked(expected, r'[0-9a-f]{64}')
    assert digest(path) == expected, 'Digest mismatch; refuse changed plan/manifest'


def main(mode):
    os.umask(0o077)
    bucket = checked(os.environ['SITE_STATE_BUCKET'], r'[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]')
    sha = checked(os.environ['GITHUB_SHA'], r'[0-9a-f]{40}')
    run = checked(os.environ['GITHUB_RUN_ID'], r'[0-9]+')
    attempt = checked(os.environ['GITHUB_RUN_ATTEMPT'], r'[0-9]+')
    uri = f'gs://{bucket}/plans/{run}/{attempt}/{sha}'
    with tempfile.TemporaryDirectory(prefix='website-infra-') as tmp:
        tmp = Path(tmp)
        log = tmp / 'terraform.log'
        plan = tmp / 'site.tfplan'
        manifest = tmp / 'manifest.json'
        inputs = tmp / 'site.tfvars.json'
        os.environ['TF_DATA_DIR'] = str(tmp / 'tfdata')
        os.environ['TF_IN_AUTOMATION'] = '1'
        os.environ['TF_INPUT'] = '0'
        lock = Path('infra/site/.terraform.lock.hcl')

        def command(args, allowed=(0,)):
            with log.open('ab') as out:
                result = subprocess.run(args, stdout=out, stderr=subprocess.STDOUT)
            if result.returncode not in allowed:
                # Preserve diagnostic output privately even on failures. Do not
                # print the log or Terraform stderr into a public workflow.
                subprocess.run(['gcloud', 'storage', 'cp', str(log), uri + '.error.log', '--if-generation-match=0'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                raise RuntimeError('Command failed; inspect the private GCS error log for this run')
            return result.returncode

        def download(remote, local, generation):
            checked(generation, r'[0-9]+')
            command(['gcloud', 'storage', 'cp', remote + '#' + generation, str(local)])

        def upload(local, remote):
            command(['gcloud', 'storage', 'cp', str(local), remote, '--if-generation-match=0'])
            with log.open('ab') as out:
                raw = subprocess.check_output(['gcloud', 'storage', 'objects', 'describe', remote, '--format=json'], stderr=out)
            generation = str(json.loads(raw)['generation'])
            checked(generation, r'[0-9]+')
            return generation

        def init():
            command(['terraform', '-chdir=infra/site', 'init', '-input=false', '-lockfile=readonly',
                     f'-backend-config=bucket={bucket}', '-backend-config=prefix=site'])
            command(['terraform', '-chdir=infra/site', 'validate'])

        if mode == 'plan':
            input_generation = os.environ['SITE_INPUTS_GENERATION']
            download(f'gs://{bucket}/inputs/site.tfvars.json', inputs, input_generation)
            config = json.loads(inputs.read_text())
            assert config['project_id'] == os.environ['SITE_PROJECT_ID'], 'Input project does not match approved environment'
            assert config['site_id'] == os.environ['SITE_ID'], 'Input site does not match approved environment'
            init()
            code = command(['terraform', '-chdir=infra/site', 'plan', '-lock-timeout=5m', '-detailed-exitcode',
                            f'-var-file={inputs}', f'-out={plan}'], allowed=(0, 2))
            # Human-readable plan stays next to the binary in PRIVATE GCS.
            review_generation = upload(log, uri + '.review.txt')
            review_sha256 = digest(log)
            outputs = {'changes': 'true' if code == 2 else 'false'}
            if code == 2:
                generation = upload(plan, uri + '.tfplan')
                data = {'commit': sha, 'run': run, 'attempt': attempt, 'terraform': '1.16.6',
                        'lock_sha256': digest(lock), 'input_generation': input_generation,
                        'review_generation': review_generation, 'review_sha256': review_sha256,
                        'input_sha256': digest(inputs), 'plan_generation': generation, 'plan_sha256': digest(plan)}
                manifest.write_text(json.dumps(data, indent=2) + '\n')
                outputs.update(plan_generation=generation, plan_sha256=digest(plan),
                               manifest_generation=upload(manifest, uri + '.manifest.json'), manifest_sha256=digest(manifest))
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                for key, value in outputs.items():
                    out.write(f'{key}={value}\n')
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
                out.write(f'Plan for `{sha}`: changes = {outputs["changes"]}. Review private `plans/{run}/{attempt}/{sha}.review.txt` at generation `{review_generation}`, SHA-256 `{review_sha256}`, and manifest before approving this run.\n')
        elif mode == 'apply':
            download(uri + '.manifest.json', manifest, os.environ['EXPECTED_MANIFEST_GENERATION'])
            verify_file(manifest, os.environ['EXPECTED_MANIFEST_SHA256'])
            data = json.loads(manifest.read_text())
            assert (data['commit'], data['run'], data['attempt'], data['terraform']) == (sha, run, attempt, '1.16.6')
            assert data['lock_sha256'] == digest(lock), 'Provider lock differs'
            assert data['plan_generation'] == os.environ['EXPECTED_PLAN_GENERATION']
            assert data['plan_sha256'] == os.environ['EXPECTED_PLAN_SHA256']
            download(uri + '.tfplan', plan, os.environ['EXPECTED_PLAN_GENERATION'])
            verify_file(plan, os.environ['EXPECTED_PLAN_SHA256'])
            init()
            # Recheck immediately before apply, after the approval and downloads.
            command(['python3', 'scripts/check-environment.py', '--head-only'])
            command(['terraform', '-chdir=infra/site', 'apply', '-lock-timeout=5m', str(plan)])
            upload(log, uri + '.apply.txt')
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
                out.write(f'Applied reviewed plan for `{sha}`. Full evidence remains in private GCS. DNS/HTTPS acceptance is separate.\n')
        else:
            raise ValueError('Expected plan or apply')


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except Exception as error:
        # Avoid accidentally printing Terraform, config, tokens or manifest data.
        print('Infrastructure operation failed. No plan/state output was published. Inspect private run evidence.', file=sys.stderr)
        sys.exit(1)

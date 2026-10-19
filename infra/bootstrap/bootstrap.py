#!/usr/bin/env python3
"""Bootstrap humano num Codespace descartável; execute --help para o percurso.

Só prepare/doctor são locais. Os restantes comandos usam um access token humano
curto, pedido sem eco e guardado apenas em /dev/shm. Não há login ADC, chaves JSON,
refresh tokens ou secrets GitHub/Codespaces; não executa cloud automaticamente.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
import zipfile

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / 'infra/bootstrap'
DEFAULT_WORKDIR = Path('/workspaces/.devcirrus-bootstrap/website-devcirrus')
RECOVERY_OBJECT = 'bootstrap-recovery/recovery.zip'
STATE_OBJECT = 'bootstrap/default.tfstate'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + '\n')


def revision():
    require(not subprocess.check_output(['git', '-C', str(REPO), 'status', '--porcelain'], text=True).strip(),
            'Use um checkout limpo de uma revisão já revista antes de preparar/executar.')
    return subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip()


def private_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'Use um caminho absoluto sem .. para o diretório privado.')
    require(path != REPO and REPO not in path.parents, 'O diretório privado tem de ficar fora do checkout.')
    for parent in [path, *path.parents]:
        require(not parent.is_symlink(), 'O diretório privado não pode atravessar symlinks.')
        require(not (parent / '.git').exists(), 'O diretório privado não pode estar dentro de outro repositório.')
    if path.exists():
        require(path.is_dir() and path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o077 == 0, 'O workspace privado tem de pertencer ao utilizador e ter modo 0700.')
    return path


def valid_inputs(data):
    require(re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', data.get('project_id', '')), 'ID de projeto inválido.')
    require(re.fullmatch(r'[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}', data.get('billing_account', '')), 'Conta de faturação inválida.')
    require(bool(data.get('org_id')) != bool(data.get('folder_id')), 'Escolha exatamente uma organização ou pasta.')
    for key in ['org_id', 'folder_id']:
        require(not data.get(key) or re.fullmatch(r'[0-9]+', data[key]), 'Parent deve ser numérico.')
    for key in ['bootstrap_state_bucket', 'site_state_bucket']:
        require(re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', data.get(key, '')), 'Nome de bucket inválido.')
    require(data['bootstrap_state_bucket'] != data['site_state_bucket'], 'Os dois buckets têm de ser distintos.')


def source_files():
    return sorted([p.name for p in SOURCE.glob('*.tf')] + ['.terraform.lock.hcl'])


def prepare(work):
    require(sys.stdin.isatty(), 'Prepare requer um terminal interativo.')
    require(not work.exists(), 'Já existe trabalho privado. Retome-o; não substitua estado existente.')
    commit = revision()
    project = input('ID candidato do novo projeto [website-devcirrus]: ').strip() or 'website-devcirrus'
    parent = input('Tipo de parent (org/folder): ').strip()
    require(parent in ['org', 'folder'], 'Escolha org ou folder.')
    data = {'project_id': project, parent + '_id': input('ID do parent aprovado: ').strip(),
            'billing_account': getpass.getpass('ID da conta de faturação aprovada (sem eco): ').strip(),
            'bootstrap_state_bucket': input('Nome aprovado do bucket de estado bootstrap: ').strip(),
            'site_state_bucket': input('Nome aprovado do bucket de estado site: ').strip()}
    valid_inputs(data)
    work.mkdir(mode=0o700, parents=True)
    (work / 'root').mkdir(mode=0o700)
    for name in source_files():
        shutil.copyfile(SOURCE / name, work / 'root' / name)
    write_json(work / 'inputs.tfvars.json', data)
    write_json(work / 'workspace.json', {'format': 1, 'source_sha': commit, 'stage': 'prepared'})
    print(f'Preparado em {work}. Reveja inputs privados e pré-requisitos; depois execute plan.')


@contextmanager
def credentials(token):
    require(token and not re.search(r'\s', token), 'Token vazio ou inválido.')
    # Fail closed: never fall back to a disk-backed temp directory.
    mounts = Path('/proc/mounts').read_text().splitlines()
    require(any(line.split()[1:3] == ['/dev/shm', 'tmpfs'] for line in mounts), '/dev/shm tem de ser tmpfs.')
    with tempfile.TemporaryDirectory(prefix='devcirrus-auth-', dir='/dev/shm') as memory:
        token_file = Path(memory) / 'access-token'
        token_file.write_text(token)
        token_file.chmod(0o600)
        env = os.environ.copy()
        for key in ['GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_CREDENTIALS', 'GOOGLE_CLOUD_KEYFILE_JSON',
                    'GCLOUD_KEYFILE_JSON', 'GOOGLE_IMPERSONATE_SERVICE_ACCOUNT', 'GOOGLE_BACKEND_CREDENTIALS',
                    'GOOGLE_BACKEND_ACCESS_TOKEN', 'GOOGLE_BACKEND_IMPERSONATE_SERVICE_ACCOUNT',
                    'CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE', 'TF_LOG', 'TF_LOG_PATH']:
            env.pop(key, None)
        for key in list(env):
            if key.startswith(('TF_CLI_ARGS', 'TF_VAR_', 'TF_LOG')) or key in ['TF_WORKSPACE', 'TF_PLUGIN_CACHE_DIR']:
                env.pop(key, None)
        env.update(GOOGLE_OAUTH_ACCESS_TOKEN=token, CLOUDSDK_CONFIG=str(Path(memory) / 'gcloud'),
                   CLOUDSDK_CORE_DISABLE_FILE_LOGGING='true', CLOUDSDK_CORE_LOG_HTTP='false',
                   CLOUDSDK_CORE_DISABLE_PROMPTS='1', TF_IN_AUTOMATION='1', TF_INPUT='0')
        try:
            yield env, token_file
        finally:
            env.pop('GOOGLE_OAUTH_ACCESS_TOKEN', None)
            # No refresh token exists. The access token expires upstream; deleting
            # this tmpfs file is local cleanup, not a claim of server-side revocation.


def backend(bucket):
    return 'terraform {\n  backend "gcs" {\n    bucket = ' + json.dumps(bucket) + '\n    prefix = "bootstrap"\n  }\n}\n'


def state_stamp(state):
    require(state.get('lineage') and isinstance(state.get('serial'), int), 'Estado sem lineage/serial válidos.')
    return {key: state[key] for key in ['lineage', 'serial']}


class Bootstrap:
    def __init__(self, work, env, token_file):
        self.work, self.env, self.token_file = work, env, token_file
        self.root = work / 'root'
        require((work / 'workspace.json').is_file(), 'Use prepare ou restore primeiro.')
        self.meta = json.loads((work / 'workspace.json').read_text())
        require(self.meta.get('format') == 1, 'Formato privado desconhecido.')
        require(self.meta['source_sha'] == revision(), 'Checkout diferente: volte à revisão guardada no workspace privado.')
        self.inputs = json.loads((work / 'inputs.tfvars.json').read_text())
        valid_inputs(self.inputs)
        for name in source_files():
            require((self.root / name).is_file() and sha(self.root / name) == sha(SOURCE / name), 'Snapshot Terraform diferente do código revisto.')
        require({p.name for p in self.root.glob('*.tf')} <= set(source_files()) | {'backend.tf'}, 'Ficheiro Terraform inesperado no snapshot.')
        if (self.root / 'backend.tf').exists():
            require((self.root / 'backend.tf').read_text() == backend(self.inputs['bootstrap_state_bucket']), 'Backend privado inesperado.')

    def save(self):
        write_json(self.work / 'workspace.json', self.meta)

    def run(self, args, allowed=(0,)):
        result = subprocess.run(args, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        result.stdout = result.stdout.replace(self.env['GOOGLE_OAUTH_ACCESS_TOKEN'].encode(), b'[REDACTED]')
        with (self.work / 'operations.log').open('ab') as log:
            log.write(result.stdout)
        require(result.returncode in allowed, f'Comando falhou; consulte {self.work / "operations.log"}. Não publique o log.')
        return result.returncode, result.stdout

    def tf(self, *args, root=None, allowed=(0,)):
        root = root or self.root
        # A fresh copy gets fresh backend metadata/provider cache; never share
        # another workspace's initialized backend during recovery verification.
        env_data = self.env.get('TF_DATA_DIR')
        self.env['TF_DATA_DIR'] = str(root / '.terraform')
        try:
            return self.run(['terraform', f'-chdir={root}', *args], allowed)
        finally:
            if env_data is None:
                self.env.pop('TF_DATA_DIR', None)
            else:
                self.env['TF_DATA_DIR'] = env_data

    def cloud(self, *args):
        return self.run(['gcloud', f'--access-token-file={self.token_file}', '--quiet', *args])

    def private_bucket(self):
        bucket = self.inputs['bootstrap_state_bucket']
        request = Request(f'https://storage.googleapis.com/storage/v1/b/{bucket}', headers={
            'Authorization': 'Bearer ' + self.env['GOOGLE_OAUTH_ACCESS_TOKEN']})
        with urlopen(request, timeout=60) as response:
            metadata = json.load(response)
        iam = metadata.get('iamConfiguration', {})
        require(iam.get('publicAccessPrevention') == 'enforced' and
                iam.get('uniformBucketLevelAccess', {}).get('enabled') and
                metadata.get('versioning', {}).get('enabled'), 'Bucket sem proteção privada/versionamento esperado; operação recusada.')

    def object(self, name, media=False):
        bucket = self.inputs['bootstrap_state_bucket']
        url = f'https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quote(name, safe="")}'
        if media:
            url += '?alt=media'
        request = Request(url, headers={'Authorization': 'Bearer ' + self.env['GOOGLE_OAUTH_ACCESS_TOKEN']})
        try:
            with urlopen(request, timeout=60) as response:
                data = response.read()
            return data if media else json.loads(data)
        except HTTPError as error:
            if error.code == 404:
                return None
            raise RuntimeError('Não foi possível consultar o objeto privado (autorização/rede).') from None

    def plan(self):
        self.meta.pop('verified', None)
        self.tf('init', '-input=false', '-lockfile=readonly')
        self.tf('validate')
        plan = self.work / 'bootstrap.tfplan'
        self.tf('plan', '-lock-timeout=5m', f'-var-file={self.work / "inputs.tfvars.json"}', f'-out={plan}')
        _, readable = self.tf('show', '-no-color', str(plan))
        (self.work / 'plan.txt').write_bytes(readable)
        self.meta.update(plan_sha256=sha(plan), inputs_sha256=sha(self.work / 'inputs.tfvars.json'), stage='planned')
        self.save()
        print(f'Plano privado: {self.work / "plan.txt"}\nSHA-256: {self.meta["plan_sha256"]}\nReveja alterações/custos/reversão e obtenha aprovação deste plano antes de apply.')

    def apply(self, approved):
        plan = self.work / 'bootstrap.tfplan'
        require(approved and approved == self.meta.get('plan_sha256') == sha(plan), 'Digest diferente do plano aprovado; execute/reveja novo plan.')
        require(self.meta['inputs_sha256'] == sha(self.work / 'inputs.tfvars.json'), 'Inputs mudaram depois do plano.')
        self.meta.pop('verified', None)
        self.meta['stage'] = 'apply-started'
        self.save()
        self.tf('apply', '-lock-timeout=5m', str(plan))
        self.meta['stage'] = 'remote' if (self.root / 'backend.tf').exists() else 'applied'
        self.save()
        print('Apply terminou. Ainda não apague o Codespace: execute migrate e verify.')

    def migrate(self):
        require(self.meta['stage'] == 'applied' and not (self.root / 'backend.tf').exists(), 'Migração inicial requer apply concluído e backend local.')
        self.private_bucket()
        require(self.object(STATE_OBJECT) is None, 'Já existe estado remoto. Pare e reconcilie a propriedade; não o substitua.')
        _, raw = self.tf('state', 'pull')
        before = state_stamp(json.loads(raw))
        (self.work / 'before-migration.tfstate').write_bytes(raw)
        self.meta.update(stage='migration-started', migration_state=before)
        self.save()
        (self.root / 'backend.tf').write_text(backend(self.inputs['bootstrap_state_bucket']))
        # Copy is automatic ONLY after proving the destination state absent.
        # This copies existing state, not an infrastructure apply approval.
        self.tf('init', '-migrate-state', '-force-copy', '-lock-timeout=5m', '-lockfile=readonly')
        _, after = self.tf('state', 'pull')
        require(state_stamp(json.loads(after)) == before, 'Migração alterou lineage/serial; não apague o Codespace.')
        self.meta['stage'] = 'remote'
        self.save()
        print('Estado migrado para GCS. Execute verify para provar a recuperação antes de apagar o Codespace.')

    def verify(self):
        require(self.meta['stage'] in ['remote', 'planned', 'verified'] and (self.root / 'backend.tf').exists(), 'Migre o estado primeiro.')
        self.private_bucket()
        self.meta.pop('verified', None)
        self.meta['stage'] = 'remote'
        self.save()
        raw = self.object(STATE_OBJECT, media=True)
        require(raw is not None, 'Estado GCS em falta.')
        stamp = state_stamp(json.loads(raw))
        _, current = self.tf('state', 'pull')
        require(state_stamp(json.loads(current)) == stamp, 'Backend diferente do estado GCS esperado.')
        archive = self.work / 'recovery.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            for name in source_files() + ['backend.tf']:
                output.write(self.root / name, 'root/' + name)
            output.write(self.work / 'inputs.tfvars.json', 'inputs.tfvars.json')
            output.writestr('workspace.json', json.dumps({'format': 1, 'source_sha': self.meta['source_sha'], 'stage': 'remote'}))
        uri = f'gs://{self.inputs["bootstrap_state_bucket"]}/{RECOVERY_OBJECT}'
        self.cloud('storage', 'cp', str(archive), uri)
        generation = str(self.object(RECOVERY_OBJECT)['generation'])
        with tempfile.TemporaryDirectory(prefix='recovery-check-', dir=self.work) as temp:
            temp = Path(temp)
            download = temp / 'recovery.zip'
            self.cloud('storage', 'cp', uri + '#' + generation, str(download))
            require(sha(download) == sha(archive), 'Backup remoto diferente; não apague o Codespace.')
            unpack(download, temp)
            recovered = Bootstrap(temp, self.env, self.token_file)
            recovered.tf('init', '-input=false', '-lockfile=readonly')
            _, restored = recovered.tf('state', 'pull')
            require(state_stamp(json.loads(restored)) == stamp, 'Estado recuperado diferente.')
            code, _ = recovered.tf('plan', '-detailed-exitcode', '-lock-timeout=5m', f'-var-file={temp / "inputs.tfvars.json"}', allowed=(0, 2))
            require(code == 0, 'O plano de recuperação tem alterações. Reveja; não apague o Codespace.')
        require(state_stamp(json.loads(self.object(STATE_OBJECT, media=True))) == stamp, 'Estado mudou durante a verificação; repita verify antes de apagar o Codespace.')
        self.meta.update(stage='verified', verified={'state': stamp, 'recovery_generation': generation,
                                                    'source_sha': self.meta['source_sha'], 'at': datetime.now(timezone.utc).isoformat()})
        self.save()
        print(f'Recuperação verificada com plano sem alterações.\nRegiste em privado: {uri}#{generation} e commit {self.meta["source_sha"]}.\nPode apagar este Codespace após guardar essa referência. Nenhuma credencial persistente foi criada pelo helper.')


def unpack(archive, destination):
    expected = {'root/' + name for name in source_files() + ['backend.tf']} | {'inputs.tfvars.json', 'workspace.json'}
    with zipfile.ZipFile(archive) as source:
        require(set(source.namelist()) == expected and len(source.namelist()) == len(expected), 'Backup contém entradas inesperadas/duplicadas; extração recusada.')
        for item in source.infolist():
            require(item.file_size <= 2_000_000 and (item.external_attr >> 16) & 0o170000 != 0o120000, 'Entrada de backup inválida.')
        source.extractall(destination)


def restore(work, bucket, generation, env, token_file):
    require(not work.exists(), 'Restore não substitui workspace existente.')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', bucket or '') and re.fullmatch(r'[0-9]+', generation or ''), 'Indique bucket e geração guardados na KB privada.')
    work.mkdir(parents=True, mode=0o700)
    archive = work / 'recovery.zip'
    result = subprocess.run(['gcloud', f'--access-token-file={token_file}', '--quiet', 'storage', 'cp',
                             f'gs://{bucket}/{RECOVERY_OBJECT}#{generation}', str(archive)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (work / 'operations.log').write_bytes(result.stdout.replace(env['GOOGLE_OAUTH_ACCESS_TOKEN'].encode(), b'[REDACTED]'))
    require(result.returncode == 0, 'Restore falhou; consulte o log privado. Nenhum apply foi executado.')
    unpack(archive, work)
    recovered = Bootstrap(work, env, token_file)
    require(recovered.inputs['bootstrap_state_bucket'] == bucket, 'Bucket do backup não corresponde à origem.')
    recovered.tf('init', '-input=false', '-lockfile=readonly')
    print('Configuração recuperada com backend GCS. Execute verify; não volte a executar o bootstrap local inicial.')


def doctor():
    require(sys.platform == 'linux' and Path('/dev/shm').is_dir(), 'Use o Codespace Linux configurado neste repositório.')
    for tool in ['terraform', 'gcloud', 'git']:
        require(shutil.which(tool), f'Ferramenta em falta: {tool}. Reconstrua o Codespace com .devcontainer.')
    result = subprocess.check_output(['terraform', 'version', '-json'], text=True)
    require(json.loads(result)['terraform_version'] == '1.16.6', 'Terraform deve ser 1.16.6.')
    sdk = subprocess.check_output(['gcloud', 'version', '--format=json'], text=True)
    require(json.loads(sdk)['Google Cloud SDK'] == '589.0.0', 'Google Cloud CLI deve ser 589.0.0.')
    print('Ferramentas prontas. Nenhuma autenticação/operação cloud foi iniciada. Leia infra/bootstrap/README.md.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog='Percurso: doctor → prepare → plan → aprovação → apply → migrate → verify → apagar Codespace. Ver README.md nesta pasta.')
    parser.add_argument('--workdir', type=Path, default=DEFAULT_WORKDIR, help='Diretório privado persistente em /workspaces, fora de Git.')
    subs = parser.add_subparsers(dest='command', required=True)
    for name, help_text in [('doctor', 'Verificar ferramentas, sem login/cloud.'), ('prepare', 'Criar snapshot e inputs privados através de perguntas.'),
                            ('plan', 'Criar plano privado; não aplica.'), ('migrate', 'Migrar estado local para GCS sem substituir estado existente.'),
                            ('verify', 'Testar backup/restauro privado e plano remoto sem alterações.')]:
        subs.add_parser(name, help=help_text)
    apply_parser = subs.add_parser('apply', help='Aplicar exatamente o plano explicitamente aprovado.')
    apply_parser.add_argument('--approved-plan-sha256', required=True, help='Digest do plano aprovado por Pedro.')
    restore_parser = subs.add_parser('restore', help='Retomar num Codespace novo a partir do backup privado.')
    restore_parser.add_argument('--bucket', required=True)
    restore_parser.add_argument('--generation', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    work = private_path(args.workdir)
    if args.command == 'doctor':
        doctor()
    elif args.command == 'prepare':
        prepare(work)
    else:
        require(sys.stdin.isatty(), 'Autenticação requer terminal interativo; não passe tokens em argumentos, pipes ou variáveis de Codespaces.')
        token = getpass.getpass('Access token curto do Cloud Shell (sem eco; não será guardado em disco): ').strip()
        with credentials(token) as (env, token_file):
            if args.command == 'restore':
                restore(work, args.bucket, args.generation, env, token_file)
            else:
                runner = Bootstrap(work, env, token_file)
                if args.command == 'apply':
                    runner.apply(args.approved_plan_sha256)
                else:
                    getattr(runner, args.command)()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        print(f'Bootstrap interrompido: {error}\nNão apague o Codespace com estado ainda não verificado. Não publique ficheiros/logs privados.', file=sys.stderr)
        sys.exit(1)

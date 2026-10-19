# Bootstrap num GitHub Codespace descartável

Este é o ponto de entrada da configuração inicial de DevCirrus. O percurso é
**abrir Codespace → preparar → planear → aprovar → aplicar → migrar/verificar
estado → apagar Codespace**. Não é necessário instalar Terraform, Google Cloud
CLI ou Docker na máquina pessoal. A implementação está preparada para revisão;
a criação real do projeto e a recuperação GCS ainda dependem de execução aprovada.

## O que faz e como funciona

O bootstrap cria o projeto dedicado `website-devcirrus` e associa-o à conta de
faturação explicitamente aprovada. Este ID é candidato, não reservado: confirmar
a disponibilidade, organização/pasta e faturação antes da execução.

| Elemento | Responsabilidade desta raiz Terraform |
|---|---|
| Projeto e APIs | Projeto protegido contra destruição, sem rede default; apenas APIs necessárias a Firebase, DNS, storage e identidade. |
| Firebase | Habilitação do projeto. Esta operação não é reversível removendo o recurso Terraform. |
| Estado privado | Dois buckets GCS europe-west1, separados para bootstrap e site, acesso uniforme, prevenção de acesso público, versões e soft delete. |
| Identidades | Três service accounts e WIF/OIDC distintos para conteúdo, plan e apply, restritos ao repositório/owner IDs, main, workflow, evento e environment. |
| Recuperação | Configuração/inputs privados e estado remoto suficientes para retomar noutro Codespace. |

O [site/domínios/Cloud DNS](../site/README.md) pertencem à fase seguinte. Releases
são da Firebase CLI. Este bootstrap não publica conteúdo, não muda NS/DS, não
compra domínios e não elimina experiências antigas. A CI não cria o próprio
projeto, faturação ou IAM: a primeira configuração é uma operação humana.

O helper `bootstrap.py` copia apenas os `.tf` e o lockfile de uma revisão limpa
para `/workspaces/.devcirrus-bootstrap/website-devcirrus`, fora do checkout e com
permissões 0700. Inputs, planos, logs e estado inicial ficam aí. `/workspaces`
persiste num stop/rebuild normal do Codespace; **apagar o Codespace elimina-o**.
Não usar `/tmp` ou a pasta do repositório para a única cópia do estado inicial.

O primeiro apply usa backend local porque o bucket ainda não existe. `migrate`
verifica que o destino está vazio, acrescenta o backend GCS na cópia privada e
migra o estado, comparando lineage/serial. Não substitui estado remoto existente.
`verify` só dá o percurso como concluído depois de:

1. Confirmar que o bucket continua privado, com versionamento.
2. Comparar o estado remoto com o backend usado pelo operador.
3. Guardar configuração/inputs no bucket bootstrap privado e descarregar a sua
   geração exata, conferindo SHA-256.
4. Inicializar uma cópia nova, recuperar o mesmo estado e obter um plano **sem
   alterações**, com os providers fixados no lockfile.

Só depois é seguro eliminar o Codespace. O backup não inclui tokens, ADC,
planos binários, caches ou uma cópia local de estado que possa competir com GCS.
Versões não correntes de estado/recuperação conservam pelo menos dez versões
mais recentes e trinta dias; soft delete é de sete dias. Não há Bucket Lock.

## Autenticação: sem chaves permanentes

Um Codespace não é um job de GitHub Actions e não recebe o seu OIDC. Além disso,
a federação do projeto ainda não existe na primeira execução. Por isso, o
bootstrap usa um **access token humano de curta duração**, obtido no Google Cloud
Shell, no browser. Não cria chaves JSON de service account, ADC, refresh tokens
ou GitHub/Codespaces secrets. Depois do bootstrap, Actions usa o WIF/OIDC criado.

O token continua a ser uma credencial sensível até expirar (normalmente cerca de
uma hora). Cola-o apenas no pedido **sem eco** do helper; nunca num comando,
argumento, ficheiro do checkout, variável persistente ou chat. O helper usa
`/dev/shm` (RAM/tmpfs) e o ambiente dos subprocessos; limpa-os no fim de cada
operação e não faz fallback para disco. Limpa também o clipboard. A limpeza
local não revoga o token no servidor; ele deixa de funcionar quando expira.
A conta humana, sessão do browser e acesso ao Codespace devem ser teus.

O operador precisa de Project Creator na organização/pasta aprovada e Billing
Account User na conta aprovada, mais permissões de configuração dos recursos no
novo projeto. Validar as políticas da organização e concessões de bootstrap;
não resolver falhas atribuindo Owner/Editor à CI. O deploy recebe Hosting Admin
no projeto dedicado, não um papel exclusivamente de upload. Plan/apply recebem
Object Admin apenas no bucket site por causa de locks e planos; não acedem ao
bucket bootstrap. Verificar permissões reais na ativação.

## Instruções práticas

### 1. Abrir o ambiente no browser

No GitHub, abre `DevCirrus/website-devcirrus` → **Code → Codespaces → … → New
with options**. Enquanto este PR não estiver integrado, seleciona a branch
`feat/codespace-bootstrap`; depois do merge autorizado, usa `main`.
Escolhe a configuração **DevCirrus — disposable bootstrap** e o tamanho pequeno
compatível (2 cores). Só tu tens acesso ao Codespace; não partilhes o terminal.

O `.devcontainer` fixa imagens oficiais por digest: Terraform 1.16.6, Google
Cloud CLI 589.0.0, Python e Git. O arranque executa apenas `doctor`, sem login ou
operações cloud. Se faltarem ferramentas, usa **Codespaces: Rebuild Container**,
não instales manualmente na tua máquina.

```sh
python3 infra/bootstrap/bootstrap.py --help
python3 infra/bootstrap/bootstrap.py doctor
git rev-parse HEAD
```

Rever a revisão executada é necessário: código de um PR pode executar comandos
com o teu token. Não injetar secrets num Codespace de código não revisto.
Codespaces tem quotas/custos próprios de computação e storage, mesmo neste
repositório público; um Codespace parado ainda ocupa storage. Confirmar a quota
na conta antes de o criar; não se promete utilização gratuita.

### 2. Confirmar inventário, custos e preparar inputs

Confirma organização/pasta, conta de faturação, disponibilidade do projeto e
nomes dos buckets, inventário de recursos/estados existentes, políticas e preços
atuais. Um 403 de leitura não demonstra disponibilidade de um ID. Importar um
objeto existente só depois de rever propriedade; nunca dois estados a geri-lo.
Mantém exportações DNS e dados pessoais na KB/armazenamento privado.

```sh
python3 infra/bootstrap/bootstrap.py prepare
```

O assistente pergunta o ID candidato, **org ou folder** (exatamente um), ID do
parent, conta de faturação (sem eco) e os dois buckets aprovados. Os valores ficam
no ficheiro privado `inputs.tfvars.json`, nunca em Git. A flag global
`--workdir /caminho/absoluto/privado` pode mudar o diretório, sempre fora de Git e
em storage persistente de `/workspaces`. Não substituas um workspace existente.

### 3. Obter o token no Cloud Shell

Abre [Google Cloud Shell](https://shell.cloud.google.com/) noutro separador do
browser, com a identidade humana aprovada. Confirma a conta ativa e obtém um
token novo imediatamente antes de cada operação:

```sh
gcloud auth list --filter=status:ACTIVE --format='value(account)'
gcloud auth print-access-token
```

Autoriza a sessão do Cloud Shell no browser quando solicitado. Não exportes uma
chave de service account. Copia só o token; volta ao terminal do Codespace e
cola-o quando o helper o pedir sem eco. Os logins do Cloud Shell são geridos no
serviço Google; não se faz `gcloud auth login` ou `application-default login` no
Codespace. Não guardar o token como Codespaces secret.

### 4. Produzir e rever o plano privado

```sh
python3 infra/bootstrap/bootstrap.py plan
```

Abre no editor do Codespace, por **File → Open File**, os ficheiros:

```text
/workspaces/.devcirrus-bootstrap/website-devcirrus/plan.txt
/workspaces/.devcirrus-bootstrap/website-devcirrus/inputs.tfvars.json
```

Confirma criação do projeto certo, parent/billing, APIs/buckets/IAM/WIF e ausência
de alterações não previstas. O helper apresenta o SHA-256 do plano. Apresenta a
Pedro o plano concreto, custos atuais, irreversibilidade Firebase e reversão,
usando canal privado para o plano/contas. **Aprovar ou fazer merge do código não
aprova este apply.** Não copiar plano, logs, estado ou inputs para comentários,
artefactos de Actions ou qualquer local público.

### 5. Aplicar apenas o plano autorizado

Depois da autorização explícita, obtém um token novo no Cloud Shell e usa o
digest exato que foi revisto:

```sh
python3 infra/bootstrap/bootstrap.py apply --approved-plan-sha256 DIGEST_APROVADO
```

O helper verifica o digest, inputs e revisão e aplica o ficheiro guardado, sem
replan nem `-auto-approve`. Se o token expirar ou houver falha parcial, **não
apagues o Codespace**: o estado local pode ser a única fonte de verdade. Obtém
token novo, consulta os logs privados, produz/revê um plano atualizado se
necessário e retoma apenas as operações autorizadas. Nunca rerun de raiz para
"resolver" conflitos de recursos nem publicar logs privados para diagnosticar.

### 6. Migrar e provar recuperação

Com token válido para cada comando:

```sh
python3 infra/bootstrap/bootstrap.py migrate
python3 infra/bootstrap/bootstrap.py verify
```

A migração usa `-migrate-state -force-copy` **só após comprovar que o objeto de
estado remoto não existe**. Isto confirma a cópia do estado que acabaste de
aplicar; não é aprovação automática de infraestrutura. Locking e `-lock-timeout=5m`
continuam ativos. Não usar `-reconfigure` como substituto desta migração.

Se uma migração for interrompida, conserva o Codespace, `before-migration.tfstate`,
`workspace.json`, root e logs privados. Compara o estado local, remoto e o
checkpoint lineage/serial antes de retomar manualmente; não forces uma nova cópia
sobre estado existente nem uses `force-unlock` sem identificar quem tem o lock.
O helper recusa a substituição para permitir essa reconciliação com segurança.

`verify` carrega um ZIP privado de recuperação, descarrega a geração exata e
simula a retoma a partir de cópia limpa com backend GCS, sem aplicar nada. Um
plano com alterações, estado divergente ou falha de leitura impede a indicação
de conclusão. Ainda não foi executada esta prova num projeto real por este PR.

### 7. Registar e apagar o Codespace

Só quando `verify` terminar com sucesso, guarda na KB privada:

- SHA do código, referência da aprovação, resultado do apply e estado remoto.
- Bucket bootstrap, objeto `bootstrap-recovery/recovery.zip` e **geração exata**
  apresentada, mais lineage/serial e a confirmação de plano sem alterações.
- Outputs técnicos necessários à fase site e às variáveis GitHub, por leitura
  privada; budget/alertas e validações de permissões ainda pendentes.

Não é preciso conservar token ou o Codespace. Limpa o clipboard, fecha sessões
que já não uses e vai a [GitHub Codespaces](https://github.com/codespaces) → menu
do Codespace → **Delete**. Parar é diferente de apagar: só apagar elimina o seu
storage. Isto não apaga projeto, buckets, faturação ou estado GCS, que continuam
sujeitos aos respetivos custos. Não foram apagados Codespaces por este PR.

### 8. Retomar futuramente num Codespace novo

Abre outro Codespace na revisão do código guardada na KB. Com token humano novo:

```sh
python3 infra/bootstrap/bootstrap.py restore --bucket BUCKET_BOOTSTRAP --generation GERACAO_GUARDADA
python3 infra/bootstrap/bootstrap.py verify
```

`restore` não substitui um workspace existente, não aplica e nunca começa com
estado local vazio contra recursos existentes. Recupera inputs/configuração da
geração privada indicada e inicializa o backend GCS. Se a revisão não coincidir,
usa primeiro o SHA guardado e tenta com um diretório privado novo. Para alterar
bootstrap mais tarde, rever a nova revisão/plano num PR e manter o backend remoto;
não executar o `prepare` inicial contra um projeto já gerido.

## Referências e limites da validação

- [Ciclo de vida do Codespace](https://docs.github.com/en/codespaces/developing-in-a-codespace/stopping-and-starting-a-codespace)
- [Eliminar Codespace](https://docs.github.com/en/codespaces/developing-in-a-codespace/deleting-a-codespace)
- [Custos Codespaces](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces)
- [Tokens curtos gcloud](https://cloud.google.com/sdk/gcloud/reference/auth/print-access-token)
- [Flag access-token-file](https://cloud.google.com/sdk/gcloud/reference#--access-token-file)
- [Backend GCS](https://developer.hashicorp.com/terraform/language/backend/gcs)

As referências das imagens oficiais/digests e o código do backend GCS foram
verificados durante a preparação deste PR.
Testes offline usam tokens fictícios e cloud simulada. Build da imagem/doctor não
provam permissões cloud, disponibilidade de IDs, criação de recursos ou recuperação
real; essas verificações pertencem à execução autorizada. Revalidar preços e
quotas antes de criar Codespace ou recursos cloud. Alertas de budget não limitam
cobranças; rollback de infraestrutura requer novo plano revisto, não destroy.

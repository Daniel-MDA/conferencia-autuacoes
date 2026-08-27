# Conferência de Autuações — 2.1

> Projeto de portfólio. Nomes de cliente, rodovia, servidor e marca foram
> substituídos por dados fictícios; a lógica, a arquitetura e o código são os
> originais.

Aplicativo desktop que substitui uma macro de Excel na conferência de
trânsitos em contramão e no acostamento de um pedágio *free flow*, até a
pasta de laudos pronta para envio à autoridade de trânsito.

```
relatório do Backoffice → [escolhe o módulo] → [confere e marca as fotos] → [1 PDF por trânsito] → remessa .zip
```

Roda inteiramente na máquina do operador, em janela nativa (Python + Flask +
pywebview). Nada trafega para fora: o único acesso de rede é a busca das
imagens no servidor de fotos configurado.

Especificação completa em [`docs/requisitos.html`](docs/requisitos.html) —
o caderno de requisitos, com as regras de negócio e o rastreio de cada
decisão; protótipo navegável em
[`prototipo/prototipo.html`](prototipo/prototipo.html), a validação de
interface feita antes de escrever a aplicação de verdade.

---

## Por que este projeto

Era um processo manual, sujeito a erro, apoiado numa macro de Excel que
travava com relatórios grandes e não deixava rastro de quem decidiu o quê.
O desafio não era só trocar Excel por uma tela: era desenhar a ferramenta
certa para quem opera sozinho, decisão após decisão, durante um turno
inteiro — sem perder trabalho se a VPN cair, sem gerar dois laudos iguais
por engano, sem depender de suporte para mudar um parâmetro.

Esse README documenta as decisões técnicas por trás disso. O processo
completo — do levantamento de requisitos ao protótipo aprovado — está nos
dois documentos linkados acima.

---

## Como rodar

### Opção A — executável único

Numa máquina com **Python 3.10 ou superior**, rode uma vez:

```
gerar_exe.bat
```

Isso empacota com PyInstaller, copia a logo (se houver uma em `logo.png` —
veja [A logo](#a-logo)) e testa o `.exe` gerado. Entregue a pasta `dist`
inteira; na máquina do operador não precisa de Python.

### Opção B — direto do código-fonte

```bash
pip install -r requirements.txt
python main.py                 # janela nativa
python main.py --demo          # imagens sintéticas, sem servidor de fotos
python main.py --navegador     # força o navegador padrão
python main.py --porta 9000    # fixa a porta do servidor local
```

`--demo` é o modo de demonstração: gera imagens sintéticas em vez de buscar
no servidor configurado, então dá para explorar a aplicação inteira sem
acesso à rede do cliente.

---

## Os dois módulos

O relatório é o mesmo nos dois casos e o operador escolhe a atividade ao
abrir a sessão. A mecânica da conferência é idêntica — os mesmos ângulos, a
mesma seleção, a mesma lista de motivos de descarte. O que a escolha define
é o **título do laudo** e a **pasta da remessa**.

| Ângulo | Nome | O que prova |
|---|---|---|
| `F` | Frontal | Onde a placa é lida |
| `P` | Panorâmica | Em que faixa o veículo estava |
| `L` | Lateral | Apoio |
| `T` | Traseira | **Em motocicleta é aqui que a placa aparece** |

A pré-seleção automática marca duas fotos: a que identifica a placa (frontal,
ou traseira em moto) e a panorâmica. O laudo exige no mínimo 2 e aceita no
máximo 8 fotos, em até 2 páginas com no máximo 4 por página.

---

## Atalhos de teclado

| Tecla | Ação |
|---|---|
| `Enter` | Autuar e ir para o próximo pendente |
| `Backspace` | Descartar — abre a lista de motivos |
| `Espaço` | Marcar ou tirar do laudo a foto em exibição |
| `←` `→` | Foto anterior e próxima, percorrendo todos os ângulos |
| `↑` `↓` | Ângulo anterior e próximo |
| `1`–`4` | Ir direto ao ângulo, na ordem das abas |
| `PgUp` `PgDn` | Trânsito anterior e próximo |
| `F` ou clique na imagem | Ampliar |
| `Esc` | Fechar a ampliação ou a caixa de motivos |

Na imagem ampliada: roda do mouse = zoom, arrastar = mover, duplo clique =
reajustar. Só campos de digitação capturam o teclado — os controles de
brilho e contraste não engolem as setas, porque ajustar o brilho e continuar
navegando pelas fotos é exatamente o que se faz numa foto traseira escura.

---

## Onde ficam os parâmetros

**Não há tela de configuração.** Tudo — servidor de imagens, ângulos,
limites, títulos do laudo, lista de motivos de descarte, pasta das remessas
— está em **`autuacao/parametros.py`**, com nomes autoexplicativos. Foi uma
escolha deliberada (não um limite de tempo): numa aplicação de operador
único, mantida por quem já mexe no código, uma tela de configuração é
superfície de erro sem ganho real. Mudou algo? Edita ali, roda `gerar_exe.bat`
e entrega de novo.

---

## As imagens

Caminho montado para cada imagem:

```
{protocolo}://{servidor}/{raiz}{AAAAMMDD}/{pasta}/{ID}-{ângulo}{nn}.jpg
```

**A pasta são os 9 primeiros caracteres do ID da transação.** Isso foi
medido sobre milhares de trânsitos reais de várias praças: a coluna `Pista`
do relatório discordava do ID em boa parte das linhas — dizia uma coisa
onde o ID dizia outra, sempre nas mesmas faixas — e quem manda é o ID. A
tentativa dupla que a primeira versão fazia não existe mais.

O ID tem 27 caracteres e é inteiramente decomponível:

```
31   02    01LFF   20260825090000   8832
│    │     │       │                └ sequência
│    │     │       └ data e hora, AAAAMMDDHHMMSS
│    │     └ pista real (5)
│    └ praça (2)
└ concessionária (2)
```

As imagens são buscadas **sob demanda**: o trânsito visível e os vizinhos
entram na fila primeiro, então a conferência começa antes de o relatório
inteiro ter sido baixado. O cache fica na pasta temporária e é **apagado ao
encerrar o executável**.

### Se as imagens não carregarem

A tela mostra o motivo e a URL tentada, e oferece **Tentar de novo** — útil
depois de religar a VPN, sem precisar recarregar a planilha.

| Mensagem | Causa provável |
|---|---|
| `sem conexão com o servidor` | VPN caída, ou servidor errado em `parametros.py` |
| `HTTP 404` | O trânsito não tem imagem nessa pasta |
| `HTTP 401` / `403` | O servidor exige autenticação |
| `a resposta não é uma imagem` | O servidor devolveu página de erro com status 200 |

---

## O laudo

Um PDF por trânsito autuado, **A4 retrato**, nomeado:

```
CONTRAMAO_NDU8490_340201LFF202608250914223401.pdf
└ módulo ┘ └placa┘ └────── ID da transação ──────┘
```

Estrutura: cabeçalho com logo e título · linha *Analisado por* · nove campos
em três linhas (Data · Hora · ID / Rodovia · Praça · Pista / Placa ·
Categoria · Velocidade) · as fotos escolhidas em 4:3, duas por linha · a
declaração de emissão da concessionária. Sem enquadramento legal, sem placa
OCR, sem comentário e sem assinatura — a autoridade de trânsito pediu só a
evidência.

Todo o desenho do documento está em **`autuacao/laudo.py`** — nenhuma outra
parte da aplicação sabe como o laudo é montado.

---

## A remessa

Uma pasta por sessão, em `Documentos\Autuacoes`:

```
CONTRAMAO_20260825_v1\
    CONTRAMAO_NDU8490_....pdf
    CONTRAMAO_RQI2E47_....pdf
    indice.csv          um registro por laudo
    remessa.zip         o anexo do e-mail
```

Gerar de novo **não sobrescreve**: cria `v2` ao lado da `v1`.

A trilha de auditoria fica em `Documentos\Autuacoes\auditoria.csv`, só de
acréscimo, com data/hora, operador do Windows, trânsito, ação, motivo e
fotos usadas.

---

## Se travar no meio da sessão

As decisões e a seleção de fotos são gravadas em disco a cada clique. Ao
reabrir o mesmo arquivo no mesmo módulo, tudo volta — e a tela de módulos
oferece a retomada direto.

---

## Quando alguma coisa dá errado

Empacotada, a aplicação roda sem console — não há para onde uma mensagem de
erro ir. Por isso ela escreve um registro em `ConferenciaAutuacoes.log`, ao
lado do executável (ou na pasta temporária, se a pasta do programa não
aceitar escrita). É o primeiro lugar para olhar.

Foi esse registro que apontou, na primeira geração do executável, que o
`import webview` estava quebrando por falta do `bottle` — a aplicação abria
no navegador em vez da janela nativa, calada. Esse tipo de falha silenciosa
é o motivo do [`verificar_build.py`](verificar_build.py): depois de gerar o
`.exe`, ele sobe o executável de verdade, confere se os arquivos embutidos
batem com o código-fonte e avisa se a janela nativa não abriu — empacotar
sem erro não garante que o programa funciona.

---

## A logo

O laudo reserva um espaço de **40 × 15,5 mm** no cabeçalho para a logo do
cliente, lida de `logo.png` na raiz do projeto (ou ao lado do `.exe`,
empacotado). É o único arquivo que fica fora do executável, de propósito —
para poder ser trocado sem recompilar.

Neste repositório o arquivo não está incluído, porque é a marca real de um
cliente. **Sem `logo.png`, a aplicação funciona normalmente**: o laudo sai
com o nome da concessionária (lido do próprio relatório) escrito no lugar
da imagem.

---

## Segurança do servidor local

A aplicação escuta em `127.0.0.1`, o que costuma passar por "seguro" e não
é: qualquer página aberta no navegador do operador consegue disparar um
`POST` para `127.0.0.1` sem precisar de CORS — o navegador bloqueia a
*leitura* da resposta, mas a requisição chega e é executada. Sem defesa, um
site qualquer poderia encerrar a sessão do operador, apagar o rascunho ou
disparar a geração de uma remessa.

`autuacao/guarda.py` implementa duas barreiras:

* **Origem** — toda requisição que muda estado precisa vir da própria
  página (o cabeçalho `Origin`, que o navegador não deixa forjar).
* **Credencial** — um token sorteado a cada execução, injetado na página e
  exigido em todo `POST`. Fecha o caso de quem chega sem `Origin` (curl,
  script local) numa porta previsível.

`GET` fica de fora de propósito: ler uma imagem não muda estado nenhum.

---

## Estrutura

```
main.py                    ponto de entrada
autuacao/
  parametros.py            TODOS os parâmetros  ← a manutenção acontece aqui
  dominio.py               Transito, Imagem, Relatorio — sem HTTP, Excel ou PDF
  relatorio.py             leitura do .xlsx do Backoffice
  imagens.py               descoberta e download sob demanda, cache
  laudo.py                 o PDF                ← o layout está aqui
  remessa.py               pasta, índice e zip
  sessao.py                estado, rascunho e trilha de auditoria
  guarda.py                proteção do servidor local (origem + token)
  servidor.py               o servidor local e a API
  janela.py                janela nativa e o plano B (navegador)
  registro.py               o log em arquivo
  web/                     interface (HTML, CSS, JS — sem dependência externa)
docs/requisitos.html       o caderno de requisitos completo
prototipo/prototipo.html   o protótipo navegável, aprovado antes da implementação
verificar_build.py         confere o .exe gerado contra o código-fonte
gerar_exe.bat              empacota, copia a logo e roda a verificação
```

---

## Stack

Python (Flask + pywebview para a janela nativa, com fallback para o
navegador), `openpyxl` para ler o relatório do Backoffice, `reportlab` +
`Pillow` para montar o PDF, PyInstaller para o executável único. Frontend
em HTML/CSS/JS sem framework nem dependência externa — a interface inteira
é servida pelo próprio backend Python.

---

## Pendência conhecida (documentada, não escondida)

O `TransactionSelectionReport` analisado não traz três dos nove campos do
laudo (`Placa`, `Categoria`, `Vel.`). A aplicação carrega assim mesmo e
avisa na tela de carga; os campos saem como `-` no PDF e o nome do arquivo
usa `SEMPLACA`. Está registrado como questão aberta no caderno de
requisitos, para ser resolvida antes de entrar em operação — decisão que
depende de qual exportação do Backoffice o cliente vai usar.

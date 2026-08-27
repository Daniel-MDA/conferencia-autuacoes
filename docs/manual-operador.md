# Conferência de Autuações — Manual do operador

*Versão 2.1 — da planilha do Backoffice até a remessa de relatórios para a PRF.*

## Visão geral

**O que esta aplicação faz.** Ela substitui a macro de Excel. Você confere os trânsitos suspeitos, escolhe as fotos que provam a infração e a aplicação monta os relatórios.

O fluxo tem cinco passos:

1. **Escolher o módulo** — Contramão ou acostamento.
2. **Carregar a planilha** — o `.xlsx` exportado do Backoffice.
3. **Conferir cada trânsito** — as fotos carregam direto do servidor.
4. **Montar a evidência** — de 2 a 8 fotos por trânsito.
5. **Gerar a remessa** — um PDF por trânsito, tudo num `.zip`.

**O que ela não faz.** Não decide e não envia nada sozinha. Quem analisa cada trânsito é o operador, quem envia o relatório é o coordenador, e quem autua é a PRF.

## Antes de começar

Três coisas precisam estar prontas:

- **Conexão com o servidor** — as fotos ficam num servidor interno. Fora da rede a conferência abre, mas nenhuma imagem chega.
- **A planilha exportada** — o relatório de transações do Backoffice, em Excel, já filtrado pelos trânsitos suspeitos.
- **O módulo decidido** — Contramão ou acostamento. A sessão inteira pertence a um só — não dá para misturar.

Onde as coisas ficam:

| O quê | Onde |
|---|---|
| O programa | `ConferenciaAutuacoes.exe` — duplo clique, sem instalar nada |
| As remessas | `Documentos \ Autuacoes \ CONTRAMAO_aaaammdd_v1` |
| A auditoria | `Documentos \ Autuacoes \ auditoria.csv` |
| Se der erro | `ConferenciaAutuacoes.log`, ao lado do programa |

**Nada sai da sua máquina.** A aplicação roda inteira no seu computador. O único acesso de rede é a busca das fotos no servidor de imagens. As fotos baixadas ficam num cache temporário e são apagadas quando você fecha o programa.

## Passo 1 — Escolher o módulo

A conferência é idêntica nos dois. O que a escolha define é o título do relatório e a pasta da remessa.

- **Análise de contramão** — veículo no sentido oposto ao da faixa. O relatório sai com o título *Comprovação de Trânsito - Contramão*.
- **Análise de acostamento** — veículo fora das faixas de rolamento. O relatório sai com o título *Comprovação de Trânsito - Acostamento*.

Trocar de módulo encerra a sessão — as decisões ficam salvas: ao reabrir a mesma planilha no mesmo módulo, tudo volta como estava.

**Retomar uma sessão.** A tela inicial mostra a última sessão gravada e diz em que pé ela está:

- *Interrompida* — você parou no meio. O botão **Retomar** volta no trânsito onde você estava.
- *Concluída* — a remessa já saiu. O botão **Reabrir** mostra a pasta que foi gerada.

## Passo 2 — Carregar a planilha

Arraste o arquivo na janela ou clique para escolher — o `.xlsx` exportado do Backoffice.

O que a aplicação confere:

- Acha o cabeçalho pelo texto *ID Transação*, com quantas linhas de filtro houver antes.
- Lê praça, período e a linha de quem gerou.
- Avisa se faltar Placa, Categoria ou Velocidade.

Depois da leitura, confira o resumo antes de começar — ele mostra quantos trânsitos vieram no arquivo e a concessionária, praça e pista lidas do cabeçalho.

## Passo 3 — A tela de conferência

É onde cada trânsito é decidido: dados do trânsito, fotos e prévia do relatório lado a lado.

## Passo 4 — Montar a evidência

- **2 fotos no mínimo** — a da placa e a panorâmica.
- **8 fotos no máximo** — em até 2 páginas, 4 por página.

Três jeitos de incluir uma foto no relatório:

- **O seletor na foto** — canto superior direito da imagem grande.
- **O quadradinho da miniatura** — na trilha, sem trocar a foto exibida.
- **A tecla Espaço** — age sobre a foto que está em exibição.

**A sugestão automática.** Assim que as fotos chegam, a aplicação já marca a frontal e a panorâmica. Ajuste o que quiser.

Como as fotos caem nas páginas do relatório: com 2 ou 4 fotos, tudo na página 1; com 6 ou 8 fotos, a página 1 leva 4 e o restante vai para a página 2.

## Passo 5 — Autuar ou descartar

- **Autuar** — tecla Enter. Só libera com pelo menos 2 fotos incluídas — se estiver travado, o motivo aparece escrito ao lado do botão.
- **Descartar** — tecla Backspace. Abre a lista de motivos — o motivo é obrigatório e vai para a auditoria, mas não sai no relatório.

Os oito motivos de descarte:

1. Veículo de emergência
2. Pedestre / ciclista
3. Veículo sem placa
4. Placa não identificada
5. Sem registro fotográfico
6. Veículo na faixa correta
7. Alteração na faixa de tráfego
8. Outros (descreva)

"Outros (descreva)" só confirma com a descrição escrita. Nos trânsitos sem nenhuma foto, a aplicação já sugere "Sem registro fotográfico".

## Passo 6 — Gerar a remessa

O que aparece na pasta gerada:

| Arquivo | O que é |
|---|---|
| `CONTRAMAO_20260825_v1/` | a pasta da remessa |
| `CONTRAMAO_<placa>_<id>.pdf` | um relatório por trânsito autuado |
| `indice.csv` | um registro por relatório |
| `remessa.zip` | é este arquivo que vai no e-mail |

A pasta abre sozinha no Explorador assim que termina.

**Nada é sobrescrito.** Se você voltar à conferência, mudar uma decisão e gerar de novo, sai uma pasta nova ao lado: `_v2`, `_v3`... A remessa que já foi para a PRF fica intacta. Depois de gerar, o botão vira **Página inicial**: a sessão acabou.

O relatório em si: A4 retrato sempre, cabeçalho com logo e título, 9 campos em 3 linhas, sem assinatura — só a evidência.

## Referência — atalhos de teclado

| Tecla | O que faz |
|---|---|
| Enter | Autuar e ir para o próximo pendente |
| Backspace | Descartar — abre a lista de motivos |
| Espaço | Incluir ou tirar do relatório a foto exibida |
| ← → | Foto anterior e próxima, do mesmo trânsito |
| ↑ ↓ | Ângulo anterior e próximo |
| 1 a 4 | Ir direto ao ângulo, na ordem das abas |
| PgUp / PgDn | Trânsito anterior e próximo |
| F | Ampliar a imagem — clicar nela faz o mesmo |
| Esc | Fechar a ampliação ou a caixa de motivos |

## Referência — quando alguma coisa dá errado

- **Sem conexão com o servidor** — religue e use *Tentar de novo*; as decisões já tomadas não se perdem.
- **HTTP 404** — este trânsito não tem imagem nessa pasta. Se nenhuma foto vier, ele fica em *Sem evidência* e não pode ser autuado.
- **HTTP 401 ou 403** — o servidor está pedindo autenticação. Chame o analista.
- **A resposta não é uma imagem** — o servidor devolveu uma página de erro. Chame o analista.

**O registro.** Se o programa não abrir, ou fechar sozinho, o motivo fica escrito em `ConferenciaAutuacoes.log`, ao lado do executável.

**Se travar no meio.** Cada decisão é gravada em disco na hora. Abra o programa de novo, escolha *Retomar* e você volta no trânsito onde parou.

## O essencial

- **2 a 8** fotos por relatório — abaixo de 2 o botão de autuar não libera.
- **F + P** é a dupla que basta — a frontal identifica; a panorâmica situa.
- **Enter** autua, **Backspace** descarta — o ciclo inteiro sai pelo teclado.
- **`.zip`** é o que vai no e-mail — gerar de novo cria uma versão ao lado.

Na dúvida, olhe a prévia à direita: ela mostra exatamente o que vai no relatório final.

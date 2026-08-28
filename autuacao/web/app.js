/* ===================================================================
   Conferência de Autuações 2.1 — interface
   =================================================================== */
'use strict';

var CFG = null;          // /api/inicio
var E = {
  tela: 'modulos',
  estado: null,          // /api/estado
  transito: null,        // /api/transito/<i>
  indice: 0,
  foto: 0,
  brilho: 100,
  contraste: 100,
  motivoEscolhido: null,
  arquivoEscolhido: null,
  lista: null,            // placas, horas e ids — fixos na sessão
  filtro: 'todos',
  busca: '',
  relogioImagens: null,
  relogioEstado: null,
  lente: { escala: 1, x: 0, y: 0, arrastando: false, ox: 0, oy: 0 }
};

var $ = function (s) { return document.querySelector(s); };
var $$ = function (s) { return [].slice.call(document.querySelectorAll(s)); };
var esc = function (s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
};

/* ─────────────────────────────────────────────────────────── rede ── */
/* A credencial desta execução, injetada pelo servidor na própria página.
   Vai em todo pedido que muda estado: sem ela o servidor recusa, o que
   fecha a porta para uma página externa disparar ações em 127.0.0.1. */
var TOKEN = (document.querySelector('meta[name="autuacao-token"]') || {})
  .content || '';

function api(url, opcoes) {
  opcoes = opcoes || {};
  opcoes.headers = opcoes.headers || {};
  opcoes.headers['X-Autuacao-Token'] = TOKEN;
  return fetch(url, opcoes).then(function (r) {
    return r.json().catch(function () { return {}; }).then(function (d) {
      if (!r.ok) throw new Error(d.erro || ('Erro ' + r.status));
      return d;
    });
  });
}
function postJson(url, corpo) {
  return api(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo || {})
  });
}

var timerAviso = null;
function avisar(msg) {
  var el = $('#aviso-flutua');
  if (!el) {
    el = document.createElement('div');
    el.id = 'aviso-flutua';
    el.className = 'aviso-flutua';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(timerAviso);
  timerAviso = setTimeout(function () { el.hidden = true; }, 4200);
}

/* ──────────────────────────────────────────────── filtro e busca ──
   Com milhares de trânsitos, percorrer um a um deixa de ser viável e a
   trilha vira um gráfico: quem navega passa a ser o filtro. As setas, o
   PgUp/PgDn e o "próximo depois de decidir" andam todos dentro do
   conjunto que está filtrado. */
var FILTROS = [
  { chave: 'todos', rotulo: 'Todos' },
  { chave: 'pendente', rotulo: 'Pendentes' },
  { chave: 'autuado', rotulo: 'Autuados' },
  { chave: 'descartado', rotulo: 'Descartados' },
  { chave: 'sem_evidencia', rotulo: 'Sem evidência' }
];
var LIMITE_TRILHA = 300;   // acima disso a trilha vira barra agregada

function combina(i) {
  var s = E.estado;
  if (E.filtro !== 'todos' && s.estados[i] !== E.filtro) return false;
  var termo = E.busca.trim().toUpperCase();
  if (!termo) return true;
  var L = E.lista || { placas: [], ids: [] };
  return ((L.placas[i] || '').toUpperCase().indexOf(termo) >= 0)
    || ((L.ids[i] || '').toUpperCase().indexOf(termo) >= 0);
}

function listaVisivel() {
  var s = E.estado, out = [];
  if (!s || !s.aberta) return out;
  for (var i = 0; i < s.total; i++) if (combina(i)) out.push(i);
  return out;
}

function vizinho(passo) {
  var vis = listaVisivel();
  if (!vis.length) return -1;
  var pos = vis.indexOf(E.indice);
  if (pos < 0) {
    /* o trânsito atual saiu do filtro: vai para o mais próximo à frente */
    for (var i = 0; i < vis.length; i++) if (vis[i] > E.indice) return vis[i];
    return vis[vis.length - 1];
  }
  var alvo = pos + passo;
  return (alvo < 0 || alvo >= vis.length) ? -1 : vis[alvo];
}

function desenharFiltros() {
  var s = E.estado;
  if (!s || !s.aberta) return;
  var conta = { todos: s.total, pendente: s.pendentes, autuado: s.autuados,
                descartado: s.descartados, sem_evidencia: s.sem_evidencia };
  var alvo = $('#filtros');
  if (alvo.children.length !== FILTROS.length) {
    alvo.innerHTML = FILTROS.map(function (f) {
      return '<button class="chip-filtro" data-filtro="' + f.chave + '">'
        + esc(f.rotulo) + ' <b></b></button>';
    }).join('');
    $$('#filtros .chip-filtro').forEach(function (b) {
      b.addEventListener('click', function () {
        E.filtro = b.dataset.filtro;
        aplicarFiltroDaLista();
      });
    });
  }
  $$('#filtros .chip-filtro').forEach(function (b) {
    var n = conta[b.dataset.filtro] || 0;
    b.querySelector('b').textContent = n;
    b.classList.toggle('on', b.dataset.filtro === E.filtro);
    b.disabled = (n === 0 && b.dataset.filtro !== E.filtro
                  && b.dataset.filtro !== 'todos');
  });

  var vis = listaVisivel();
  var caixa = $('#pos-lista');
  if (!vis.length) {
    caixa.className = 'pos-lista vazio';
    caixa.textContent = 'nada encontrado';
  } else {
    var pos = vis.indexOf(E.indice);
    caixa.className = 'pos-lista';
    caixa.textContent = (pos >= 0 ? (pos + 1) + ' de ' : '')
      + vis.length + (vis.length === 1 ? ' trânsito' : ' trânsitos');
  }
  $('#ir-numero').max = s.total;
}

/* Nome longo de proposito: `aplicarFiltro` ja existe neste arquivo e quer
   dizer outra coisa — o brilho e o contraste da imagem. Duas funcoes com o
   mesmo nome se anulam em silencio, e foi o que aconteceu na primeira
   versao disto: a busca ajustava o brilho da foto. */
function aplicarFiltroDaLista() {
  desenharFiltros();
  desenharTrilha();
  desenharNav();
  var vis = listaVisivel();
  if (vis.length && vis.indexOf(E.indice) < 0) irParaTransito(vis[0]);
}

/* ────────────────────────────────────────────── pergunta na própria tela
   O confirm() do navegador trava a página, ignora o tema e no WebView2 se
   comporta de um jeito difícil de prever. */
function perguntar(titulo, texto, rotuloSim) {
  return new Promise(function (resolve) {
    $('#pergunta-titulo').textContent = titulo;
    $('#pergunta-texto').textContent = texto;
    $('#pergunta-sim').textContent = rotuloSim || 'Continuar';
    var fim = function (r) {
      $('#cortina-pergunta').classList.remove('on');
      $('#pergunta-sim').onclick = null;
      $('#pergunta-nao').onclick = null;
      resolve(r);
    };
    $('#pergunta-sim').onclick = function () { fim(true); };
    $('#pergunta-nao').onclick = function () { fim(false); };
    abrirCortina('cortina-pergunta');
    $('#pergunta-nao').focus();
  });
}

/* ────────────────────────────────────────────────────────── telas ── */
function mostrar(tela) {
  E.tela = tela;
  ['modulos', 'carga', 'conferencia', 'resumo'].forEach(function (t) {
    $('#tela-' + t).classList.toggle('on', t === tela);
  });
  var dentro = (tela === 'conferencia' || tela === 'resumo');
  $('#contadores').hidden = !dentro;
  $('#arquivo').hidden = !dentro;
  $('#chip-modulo').hidden = (tela === 'modulos');
  $('#btn-finalizar').hidden = (tela !== 'conferencia');
  $('#btn-trocar-modulo').hidden = (tela === 'modulos');

  clearInterval(E.relogioEstado);
  if (tela === 'conferencia') {
    E.relogioEstado = setInterval(atualizarEstado, 2500);
  }
  if (tela === 'resumo') carregarResumo();
}

/* ───────────────────────────────────────────────────── T1 módulos ── */
function desenharModulos() {
  $('#hub-cartoes').innerHTML = CFG.modulos.map(function (m) {
    return '<button class="cartao-modulo" data-modulo="' + m.chave + '">'
      + '<div class="cm-pista cm-' + m.chave + '"></div>'
      + '<div class="cm-corpo"><h2>Análise de ' + esc(m.nome.toLowerCase()) + '</h2>'
      + '<p>' + esc(m.descricao) + '<br>Relatório: <em>' + esc(m.titulo_laudo) + '</em>.</p>'
      + '<div class="entrar">Começar ›</div></div></button>';
  }).join('');

  $$('#hub-cartoes .cartao-modulo').forEach(function (b) {
    b.addEventListener('click', function () { escolherModulo(b.dataset.modulo); });
  });

  var r = E.estado && E.estado.rascunho;
  var faixa = $('#retomar');
  if (r) {
    var concluida = !!r.remessa;
    faixa.hidden = false;
    faixa.innerHTML = '<span class="marca-pista mp-' + r.modulo + '"></span>'
      + '<div><b>' + (concluida ? 'Sessão concluída em ' : 'Sessão interrompida em ')
      + esc(r.quando) + '</b> — ' + esc(r.modulo_nome) + ' · '
      + esc(r.nome_arquivo) + ' · '
      + r.decididos + (r.decididos === 1 ? ' decidido' : ' decididos')
      + (concluida ? '<br><span class="remessa-feita">Remessa gerada em '
          + esc(r.remessa) + '</span>' : '')
      + '</div>'
      + '<span class="separa"></span>'
      + '<button class="btn btn-mini" id="btn-retomar">'
      + (concluida ? 'Reabrir' : 'Retomar') + '</button>'
      + '<button class="btn btn-mini" id="btn-esquecer">Descartar</button>';
    $('#btn-retomar').addEventListener('click', function () {
      abrirSessao(r.modulo, r.arquivo, null);
    });
    $('#btn-esquecer').addEventListener('click', function () {
      postJson('/api/descartar-rascunho').then(function (d) {
        E.estado = d.estado; desenharModulos();
      });
    });
  } else {
    faixa.hidden = true;
  }
}

function escolherModulo(chave) {
  E.moduloEscolhido = chave;
  var m = CFG.modulos.filter(function (x) { return x.chave === chave; })[0];
  $('#nome-modulo').textContent = m.nome;
  $('#marca-modulo').className = 'marca-pista mp-' + chave;
  resetarCarga();
  mostrar('carga');
}

/* ────────────────────────────────────────────────────── T2 carga ── */
function resetarCarga() {
  E.arquivoEscolhido = null;
  $('#resumo-carga').hidden = true;
  $('#carga-erro').hidden = true;
  $('#carga-lendo').hidden = true;
  $('#dz-titulo').textContent = 'Arraste o arquivo aqui';
  $('#dz-sub').textContent = 'ou clique para escolher — .xlsx exportado do Backoffice';
}

function pedirArquivo() {
  if (CFG.tem_janela_nativa) {
    postJson('/api/escolher-arquivo').then(function (d) {
      if (d.disponivel && d.caminho) abrirSessao(E.moduloEscolhido, d.caminho, null);
      else if (!d.disponivel) $('#arquivo-input').click();
    }).catch(function () { $('#arquivo-input').click(); });
  } else {
    $('#arquivo-input').click();
  }
}

function abrirSessao(modulo, caminho, arquivo) {
  E.moduloEscolhido = modulo;
  var m = CFG.modulos.filter(function (x) { return x.chave === modulo; })[0];
  $('#nome-modulo').textContent = m.nome;
  $('#marca-modulo').className = 'marca-pista mp-' + modulo;
  mostrar('carga');

  $('#carga-erro').hidden = true;
  $('#resumo-carga').hidden = true;
  $('#carga-lendo').hidden = false;

  var pedido;
  if (arquivo) {
    var fd = new FormData();
    fd.append('modulo', modulo);
    fd.append('arquivo', arquivo);
    pedido = api('/api/sessao', { method: 'POST', body: fd });
  } else {
    pedido = postJson('/api/sessao', { modulo: modulo, caminho: caminho });
  }

  pedido.then(function (d) {
    $('#carga-lendo').hidden = true;
    E.estado = d.estado;
    E.filtro = 'todos';
    E.busca = '';
    $('#busca').value = '';
    return carregarLista().then(function () { mostrarResumoCarga(d.resumo); });
  }).catch(function (e) {
    $('#carga-lendo').hidden = true;
    $('#carga-erro').hidden = false;
    $('#carga-erro').textContent = e.message;
  });
}

/* placas, horas e ids não mudam na sessão: uma busca só, e o filtro e a
   busca por placa passam a rodar inteiros no cliente */
function carregarLista() {
  return api('/api/lista').then(function (l) { E.lista = l; })
    .catch(function () { E.lista = { placas: [], horas: [], ids: [] }; });
}


function mostrarResumoCarga(r) {
  $('#dz-titulo').textContent = r.arquivo.split(/[\\/]/).pop();
  $('#dz-sub').textContent = r.total + ' trânsitos · lido sem erro';

  var itens = [
    ['Trânsitos', r.total],
    ['Concessionária', r.concessionaria || '—'],
    ['Praças', r.pracas.length ? r.pracas.join(', ') : '—'],
    ['Pistas', r.pistas.length ? r.pistas.join(', ') : '—']
  ];
  $('#rc-grade').innerHTML = itens.map(function (i) {
    return '<div class="rc-item" title="' + esc(i[1]) + '"><em>' + esc(i[0])
      + '</em><b>' + esc(i[1]) + '</b></div>';
  }).join('');

  var avisos = [];
  if (r.colunas_faltando && r.colunas_faltando.length) {
    avisos.push('<b>Esta planilha não traz ' + r.colunas_faltando.join(', ')
      + '.</b> Esses campos vão sair como “-” no relatório.');
  }
  if (r.restauradas) {
    avisos.push('<b>' + r.restauradas + ' decisões restauradas</b> da sessão anterior.');
  }
  if (r.contramao_sinalizados) {
    avisos.push(r.contramao_sinalizados + ' trânsitos vêm com <code>Direção = Contramão</code>.');
  }
  $('#rc-aviso').hidden = !avisos.length;
  $('#rc-aviso').innerHTML = avisos.join('<br>');

  $('#resumo-carga').hidden = false;
}

/* ─────────────────────────────────────────────── T3 conferência ── */
function irParaTransito(indice) {
  clearTimeout(E.relogioImagens);
  return api('/api/transito/' + indice).then(function (t) {
    E.transito = t;
    E.indice = t.indice;
    E.foto = 0;
    desenharConferencia();
    if (!t.imagens_buscadas) esperarImagens();
    return t;
  }).catch(function (e) { avisar(e.message); });
}

function recarregarTransito(manterFoto) {
  return api('/api/transito/' + E.indice).then(function (t) {
    var antes = E.foto;
    E.transito = t;
    if (manterFoto) E.foto = Math.min(antes, Math.max(0, fotos().length - 1));
    desenharConferencia();
    return t;
  });
}

function esperarImagens() {
  clearTimeout(E.relogioImagens);
  E.relogioImagens = setTimeout(function () {
    api('/api/transito/' + E.indice).then(function (t) {
      if (t.indice !== E.indice) return;
      E.transito = t;
      desenharConferencia();
      if (!t.imagens_buscadas) esperarImagens();
    }).catch(function () { /* silencioso: a espera continua */ });
  }, 700);
}

function fotos() {
  return (E.transito && E.transito.imagens) ? E.transito.imagens : [];
}

function desenharConferencia() {
  desenharFiltros();
  desenharTrilha();
  desenharDados();
  desenharAbas();
  desenharPalco();
  desenharTira();
  desenharPrevia();
  desenharNav();
  desenharContadores();
}

/* Até LIMITE_TRILHA trânsitos cada botão é um trânsito. Acima disso um
   botão vira uma faixa: com 3.419 itens cada um teria menos de um pixel e
   a trilha deixaria de ser clicável. A cor da faixa mostra o que ainda
   falta — pendente ganha de tudo, porque é o que interessa. */
function desenharTrilha() {
  var s = E.estado;
  if (!s || !s.aberta) return;
  var tr = $('#trilha');
  var agrupada = s.total > LIMITE_TRILHA;
  var n = agrupada ? LIMITE_TRILHA : s.total;
  var L = E.lista || { placas: [], horas: [] };

  if (tr.children.length !== n || tr.dataset.total != s.total) {
    tr.dataset.total = s.total;
    tr.innerHTML = '';
    for (var k = 0; k < n; k++) {
      var b = document.createElement('button');
      b.type = 'button';
      b.dataset.k = k;
      b.addEventListener('click', function () {
        var faixa = limitesDaFaixa(parseInt(this.dataset.k, 10));
        var vis = listaVisivel();
        for (var j = 0; j < vis.length; j++) {
          if (vis[j] >= faixa[0] && vis[j] < faixa[1]) {
            irParaTransito(vis[j]); return;
          }
        }
        irParaTransito(faixa[0]);
      });
      tr.appendChild(b);
    }
  }

  [].forEach.call(tr.children, function (b, k) {
    var faixa = limitesDaFaixa(k);
    var estado = resumoDaFaixa(faixa);
    var aqui = E.indice >= faixa[0] && E.indice < faixa[1];
    var dentro = false;
    for (var i = faixa[0]; i < faixa[1] && !dentro; i++) dentro = combina(i);
    b.className = 't-' + estado + (aqui ? ' t-atual' : '')
      + (dentro ? '' : ' fora');
    b.title = agrupada
      ? ('trânsitos ' + (faixa[0] + 1) + ' a ' + faixa[1])
      : ((faixa[0] + 1) + ' · ' + (L.placas[faixa[0]] || 'sem placa')
         + ' · ' + (L.horas[faixa[0]] || ''));
  });

  $('#trilha-nota').textContent = agrupada
    ? ('cada faixa cobre ' + Math.ceil(s.total / n) + ' trânsitos')
    : '';
}

function limitesDaFaixa(k) {
  var s = E.estado;
  var n = s.total > LIMITE_TRILHA ? LIMITE_TRILHA : s.total;
  var ini = Math.floor(k * s.total / n);
  var fim = Math.floor((k + 1) * s.total / n);
  return [ini, Math.max(fim, ini + 1)];
}

function resumoDaFaixa(faixa) {
  var e = E.estado.estados, tem = {};
  for (var i = faixa[0]; i < faixa[1]; i++) tem[e[i]] = true;
  if (tem.pendente) return 'pendente';
  if (tem.sem_evidencia) return 'sem_evidencia';
  if (tem.descartado) return 'descartado';
  if (tem.autuado) return 'autuado';
  return 'pendente';
}

function desenharDados() {
  var t = E.transito;
  if (!t) return;

  var grupos = [
    ['Identificação', [
      { r: 'Placa', v: t.placa, forte: true },
      { r: 'Categoria', v: t.categoria, forte: true },
      { r: 'Velocidade', v: t.velocidade ? t.velocidade + ' km/h' : '' }
    ]],
    ['Onde', [
      { r: 'Praça', v: t.praca_completa || t.praca, larga: true },
      { r: 'Pista', v: t.pista },
      { r: 'Faixa', v: t.faixa_descrita || t.faixa, forte: true },
      { r: 'Direção', v: t.direcao, forte: t.eh_contramao },
      /* em contramão pista e sentido saem invertidos (RN-19) — destacado
         porque é o que vai no documento e o que conferir na foto */
      { r: 'Sentido do deslocamento', v: t.deslocamento,
        forte: t.eh_contramao, larga: true }
    ]],
    ['Quando', [
      { r: 'Data', v: t.data },
      { r: 'Hora', v: t.hora }
    ]],
    ['Transação', [
      { r: 'ID', v: t.id, larga: true },
      { r: 'Pasta no servidor', v: t.pasta_servidor, larga: true },
      {
        r: 'Imagens',
        v: t.imagens_buscadas ? (t.imagens.length + ' recuperadas') : 'buscando…'
      }
    ]],
    ['Complementares', [
      { r: 'Concessionária', v: E.estado.concessionaria, fraco: true },
      { r: 'Modo', v: t.modo, fraco: true },
      { r: 'Estado', v: t.estado_tr, fraco: true },
      { r: 'Status', v: t.status, fraco: true },
      { r: 'T. Pago', v: t.t_pago, fraco: true },
      { r: 'F. Pago', v: t.f_pago, fraco: true }
    ]]
  ];

  $('#grade-dados').innerHTML = grupos.map(function (g) {
    return '<div class="pd-grupo">' + esc(g[0]) + '</div>'
      + g[1].map(function (c) {
        var valor = (c.v === null || c.v === undefined || c.v === '') ? '—' : c.v;
        var cls = 'pd-linha' + (c.forte ? ' destaque' : '')
          + (c.fraco ? ' fraco' : '') + (c.larga ? ' larga' : '');
        return '<div class="' + cls + '" title="' + esc(valor) + '"><em>'
          + esc(c.r) + '</em><b>' + esc(valor) + '</b></div>';
      }).join('');
  }).join('');

  /* só os alertas: a posição na sessão já está na navegação acima das fotos */
  var selos = [];
  if (t.eh_moto) {
    selos.push('<span class="selo selo-alerta">Motocicleta — a traseira '
      + 'identifica a placa</span>');
  }
  if (t.placa_diverge) {
    selos.push('<span class="selo selo-alerta">Placa diverge do OCR ('
      + esc(t.placa_ocr) + ')</span>');
  }
  if (t.imagens_buscadas && !t.imagens.length) {
    selos.push('<span class="selo selo-alerta">Sem evidência — '
      + esc(t.erro_busca || 'nenhuma imagem') + '</span>');
  }
  if (t.decisao === 'autuado') {
    selos.push('<span class="selo selo-ok">Autuado</span>');
  }
  if (t.decisao === 'descartado') {
    selos.push('<span class="selo selo-no">Descartado: ' + esc(t.motivo)
      + (t.descricao ? ' — ' + esc(t.descricao) : '') + '</span>');
  }
  $('#selos').innerHTML = selos.join('');
}

function desenharAbas() {
  var t = E.transito;
  if (!t) return;
  var cont = t.contagem_angulos || {};
  $('#abas').innerHTML = t.ordem_angulos.map(function (a, n) {
    var qtd = cont[a] || 0;
    var atual = fotos()[E.foto];
    var ativo = atual && atual.angulo === a;
    var quantas = qtd === 0 ? 'nenhuma foto' : (qtd === 1 ? '1 foto' : qtd + ' fotos');
    return '<button class="aba' + (ativo ? ' on' : '') + '" data-ang="' + a + '"'
      + (qtd ? '' : ' disabled') + ' title="' + esc(CFG.angulos[a]) + ' · '
      + quantas + ' · tecla ' + (n + 1) + '">'
      + a + '<span>' + (qtd || '—') + '</span></button>';
  }).join('');

  $$('#abas .aba').forEach(function (b) {
    b.addEventListener('click', function () { irParaAngulo(b.dataset.ang); });
  });
}

function irParaAngulo(ang) {
  var lista = fotos();
  for (var i = 0; i < lista.length; i++) {
    if (lista[i].angulo === ang) { E.foto = i; desenharConferencia(); return; }
  }
}

function mudarFoto(passo) {
  var lista = fotos();
  if (lista.length < 2) return;
  E.foto = (E.foto + passo + lista.length) % lista.length;
  desenharConferencia();
}

/* O id do trânsito faz parte da URL de propósito. Sem ele a URL era só
   índice + código — a mesma para o primeiro trânsito de qualquer planilha
   — e a resposta é marcada como imutável por 24 h: ao abrir outra planilha
   sem fechar o programa, o navegador servia a foto guardada da anterior, de
   outro veículo. O servidor confere o id contra o índice e recusa se
   divergirem. */
function urlImagem(codigo, largura) {
  var t = E.transito;
  var u = '/api/imagem/' + E.indice + '/' + codigo
    + '?t=' + encodeURIComponent(t ? t.id : '');
  return largura ? (u + '&w=' + largura) : u;
}

function desenharPalco() {
  var t = E.transito, lista = fotos(), palco = $('#palco');
  var antigo = palco.querySelector('img, .palco-vazio');
  if (antigo) antigo.remove();

  var varias = lista.length > 1;
  $('#foto-ant').hidden = !varias;
  $('#foto-prox').hidden = !varias;
  $('#pos-foto').hidden = !lista.length;
  $('#rebuscar').hidden = !(t && t.imagens_buscadas && !lista.length);

  if (!lista.length) {
    $('#seletor-foto').hidden = true;
    var v = document.createElement('div');
    v.className = 'palco-vazio';
    if (!t || !t.imagens_buscadas) {
      v.innerHTML = '<span class="girando" style="display:inline-block"></span>'
        + '<br>Buscando as imagens no servidor…';
    } else {
      v.innerHTML = '<b>Sem evidência</b>'
        + esc(t.erro_busca || 'Nenhuma imagem recuperada para este trânsito.')
        + (t.url_tentada ? '<code>' + esc(t.url_tentada) + '</code>' : '')
        + 'Este trânsito não pode ser autuado.';
    }
    palco.appendChild(v);
    return;
  }

  if (E.foto >= lista.length) E.foto = 0;
  var img = lista[E.foto];
  var el = document.createElement('img');
  el.src = urlImagem(img.codigo);
  el.alt = img.nome + ' — ' + img.codigo;
  el.style.filter = 'brightness(' + (E.brilho / 100) + ') contrast('
    + (E.contraste / 100) + ')';
  el.addEventListener('click', abrirLente);
  palco.insertBefore(el, palco.firstChild);

  $('#pos-foto').textContent = (E.foto + 1) + ' / ' + lista.length + ' · '
    + img.codigo + ' · ' + img.nome;

  var dentro = t.selecionadas.indexOf(img.codigo) >= 0;
  var sel = $('#seletor-foto');
  sel.hidden = false;
  sel.className = 'seletor-foto' + (dentro ? ' dentro' : '');
  sel.querySelector('.txt').textContent =
    dentro ? 'No relatório' : 'Incluir no relatório';
}

function desenharTira() {
  var t = E.transito, lista = fotos();
  var alvo = $('#tira-lista'), conta = $('#conta-sel');
  if (!t) return;

  conta.textContent = t.selecionadas.length + ' de ' + CFG.max_fotos;
  if (!$('#tira-previa-oculta')) {
    var nota = document.createElement('span');
    nota.id = 'tira-previa-oculta';
    nota.className = 'previa-oculta';
    nota.textContent = 'prévia oculta — alargue a janela';
    $('.tira-cab .separa').insertAdjacentElement('beforebegin', nota);
  }
  conta.classList.toggle('alerta',
    t.selecionadas.length >= CFG.max_fotos || t.selecionadas.length < CFG.min_fotos);

  if (!lista.length) {
    alvo.innerHTML = '<span style="font-size:11.5px;color:var(--suave);padding:14px 2px">'
      + (t.imagens_buscadas ? 'Nenhuma imagem para escolher.' : 'Buscando…') + '</span>';
    return;
  }

  alvo.innerHTML = lista.map(function (img, i) {
    var sel = t.selecionadas.indexOf(img.codigo) >= 0;
    var pos = t.selecionadas.indexOf(img.codigo) + 1;
    var pag = Math.floor((pos - 1) / CFG.fotos_por_pagina) + 1;
    return '<button class="mini-foto' + (sel ? ' sel' : '') + (i === E.foto ? ' atual' : '')
      + '" data-codigo="' + img.codigo + '" aria-pressed="' + sel + '" title="'
      + 'Ver ' + esc(img.nome) + ' · ' + img.codigo + '">'
      + '<img src="' + urlImagem(img.codigo, 160) + '" alt="">'
      + '<span class="tique" role="button" tabindex="-1" '
      + 'title="Incluir no relatório / tirar">✓</span>'
      + '<span class="ordem">' + pos + ' · p' + pag + '</span>'
      + '<span class="rot">' + img.codigo + '</span></button>';
  }).join('');

  /* Duas funções separadas na mesma miniatura: a IMAGEM navega, o
     QUADRADINHO inclui. Antes o clique na miniatura fazia as duas coisas e o
     operador acabava incluindo foto sem querer, só de olhar. */
  $$('#tira-lista .mini-foto').forEach(function (b) {
    b.addEventListener('click', function () {
      var lista2 = fotos();
      for (var i = 0; i < lista2.length; i++) {
        if (lista2[i].codigo === b.dataset.codigo) { E.foto = i; break; }
      }
      desenharConferencia();
    });
  });
  $$('#tira-lista .tique').forEach(function (cx) {
    cx.addEventListener('click', function (ev) {
      ev.stopPropagation();          /* não troca a foto em exibição */
      alternarFoto(cx.parentNode.dataset.codigo);
    });
  });
}

function alternarFoto(codigo) {
  postJson('/api/foto', { indice: E.indice, acao: 'alternar', codigo: codigo })
    .then(function (t) { E.transito = t; desenharConferencia(); })
    .catch(function (e) { avisar(e.message); });
}

function acaoSelecao(acao) {
  postJson('/api/foto', { indice: E.indice, acao: acao })
    .then(function (t) { E.transito = t; desenharConferencia(); })
    .catch(function (e) { avisar(e.message); });
}

/* ── prévia embutida ───────────────────────────────────────────────── */
function desenharPrevia() {
  var t = E.transito, alvo = $('#previa-rolagem');
  if (!t) return;
  var sel = t.selecionadas;

  if (!sel.length) {
    $('#tag-pag').textContent = '';
    alvo.innerHTML = '<div class="pv-folha"><div class="pv-vazio">'
      + 'Nenhuma foto incluída.<br>O relatório precisa de pelo menos ' + CFG.min_fotos
      + ' — a que identifica a placa e a panorâmica.</div></div>';
    return;
  }

  var valores = {
    data: t.data, hora: t.hora, id: t.id,
    data_e_hora: (t.data + ' ' + t.hora).trim(),
    rodovia: CFG.rodovia, praca: t.praca, pista: t.pista,
    praca_completa: t.praca_completa,
    faixa_descrita: t.faixa_descrita,
    deslocamento: t.deslocamento,
    placa: t.placa, categoria: t.categoria,
    velocidade: t.velocidade ? t.velocidade + ' km/h' : ''
  };
  var blocoDados = '<div class="pv-rot">Dados</div><div class="pv-dados">'
    + CFG.campos_laudo.map(function (c) {
      var v = valores[c[1]] || '-';
      return '<div class="pv-campo" title="' + esc(v) + '"><em>' + esc(c[0])
        + '</em><b>' + esc(v) + '</b></div>';
    }).join('') + '</div>';

  var porCodigo = {};
  fotos().forEach(function (i) { porCodigo[i.codigo] = i; });

  var paginas = [];
  for (var i = 0; i < sel.length; i += CFG.fotos_por_pagina) {
    paginas.push(sel.slice(i, i + CFG.fotos_por_pagina));
  }
  $('#tag-pag').textContent = paginas.length + (paginas.length > 1 ? ' páginas' : ' página')
    + ' · ' + sel.length + (sel.length > 1 ? ' fotos' : ' foto');

  alvo.innerHTML = paginas.map(function (pg, n) {
    return '<div class="pv-folha">'
      + (paginas.length > 1 ? '<span class="pv-selo">pág. ' + (n + 1) + '</span>' : '')
      + '<div class="pv-cab"><div class="pv-logo">logo</div>'
      + '<div class="pv-titulo">' + esc(E.estado.titulo_laudo.toUpperCase()) + '</div></div>'
      + '<div class="pv-origem">' + esc(E.estado.linha_analise || '') + '</div>'
      + blocoDados
      + '<div class="pv-rot">Evidência fotográfica</div>'
      + '<div class="pv-fotos">'
      + pg.map(function (codigo) {
        var img = porCodigo[codigo] || { nome: '', arquivo: codigo };
        return '<div class="pv-cel"><div class="pv-foto">'
          + '<img src="' + urlImagem(codigo, 320) + '" alt=""></div>'
          + '<span>' + esc(img.nome) + ' · ' + esc(img.arquivo) + '</span></div>';
      }).join('')
      + '</div>'
      + '<div class="pv-decl"><b>Emitido por ' + esc(CFG.concessionaria) + '</b><br>'
      + esc(CFG.declaracao) + '</div></div>';
  }).join('') + '<p class="previa-nota">' + notaPrevia(sel.length) + '</p>';
}

function notaPrevia(n) {
  if (n < CFG.min_fotos) {
    var faltam = CFG.min_fotos - n;
    return '<b>Falta ' + faltam + (faltam > 1 ? ' fotos' : ' foto')
      + '</b> para o relatório poder ser gerado.';
  }
  var pgs = Math.ceil(n / CFG.fotos_por_pagina);
  return '<b>' + n + ' fotos</b> em ' + pgs + (pgs > 1 ? ' páginas' : ' página')
    + ', até ' + CFG.fotos_por_pagina + ' por página. Máximo de ' + CFG.max_fotos + '.';
}

function desenharNav() {
  var t = E.transito, s = E.estado;
  if (!t || !s) return;
  $('#contador').textContent = (E.indice + 1) + ' / ' + s.total;
  $('#ant').disabled = vizinho(-1) < 0;
  $('#prox').disabled = vizinho(1) < 0;

  $('#btn-autuar').disabled = !!t.bloqueio;
  var av = $('#aviso-bloqueio');
  av.hidden = !t.bloqueio;
  if (t.bloqueio) av.textContent = t.bloqueio;
}

function desenharContadores() {
  var s = E.estado;
  if (!s || !s.aberta) return;
  $('#c-ok').textContent = s.autuados;
  $('#c-no').textContent = s.descartados;
  $('#c-pend').textContent = s.pendentes + s.sem_evidencia;
  $('#arquivo').textContent = s.arquivo;

  /* quantas imagens já chegaram: sem isso o operador não sabe se vale
     esperar ou se o servidor não vai responder mesmo */
  var faltam = s.buscadas < s.total;
  $('#pill-imagens').hidden = !faltam;
  if (faltam) {
    $('#c-img').textContent = s.buscadas;
    $('#c-img-total').textContent = s.total;
  }
}

function atualizarEstado() {
  api('/api/estado').then(function (s) {
    if (!s.aberta) return;
    var antes = E.estado ? E.estado.buscadas : -1;
    E.estado = s;
    desenharFiltros();
    desenharTrilha();
    desenharContadores();
    if (s.aviso_rede && s.pendentes && antes !== s.buscadas) {
      /* aviso discreto: não interrompe a conferência */
    }
  }).catch(function () { /* silencioso */ });
}

/* ── decisão ───────────────────────────────────────────────────────── */
function autuar() {
  var t = E.transito;
  if (!t || $('#btn-autuar').disabled) return;
  /* RF-35: divergência entre a placa do relatório e a leitura automática
     não impede autuar, mas não pode passar despercebida — é a placa que
     identifica o veículo no documento que vai para a PRF. */
  if (t.placa_diverge) {
    perguntar('Placa divergente',
      'O relatório traz a placa ' + t.placa + ' e a leitura automática '
      + 'devolveu ' + t.placa_ocr + '. O relatório sai com '
      + t.placa + '. Confira nas fotos antes de seguir.',
      'Autuar assim mesmo').then(function (ok) {
        if (ok) decidir('autuado');
      });
    return;
  }
  decidir('autuado');
}

function decidir(desfecho, motivo, descricao) {
  /* #btn-autuar fica com o foco depois do clique; sem tirar o foco aqui,
     o Espaço do próximo trânsito vira um clique nativo no botão (que
     continua o mesmo elemento na tela seguinte) em vez de marcar a foto. */
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
  postJson('/api/decisao', {
    indice: E.indice, decisao: desfecho,
    motivo: motivo || '', descricao: descricao || ''
  }).then(function (d) {
    E.estado = d.estado;
    proximoPendente();
  }).catch(function (e) { avisar(e.message); });
}

/* Sem evidência conta como não decidido: o trânsito não sumiu da lista de
   trabalho, ainda precisa de um descarte com motivo. É o mesmo critério do
   contador de pendentes no rodapé. */
function naoDecidido(i) {
  var e = E.estado.estados[i];
  return e === 'pendente' || e === 'sem_evidencia';
}

/* Para onde ir depois de decidir. A busca anda para a frente e dá a volta,
   então concluir o último cai no primeiro que ainda falta decidir — e não
   no primeiro da lista, que em geral já estava resolvido. Não sobrando
   nada para decidir, o que resta é gerar a remessa. */
function proximoPendente() {
  var s = E.estado;

  if (E.filtro === 'todos' || E.filtro === 'pendente') {
    for (var d = 1; d <= s.total; d++) {
      var i = (E.indice + d) % s.total;
      if (naoDecidido(i) && combina(i)) { irParaTransito(i); return; }
    }
  } else {
    /* navegando por decididos: segue na lista filtrada, sem tirar o
       operador do lugar enquanto houver o que ver ali */
    var adiante = vizinho(1);
    if (adiante >= 0) { irParaTransito(adiante); return; }
  }

  /* nada dentro do filtro: o primeiro que falta decidir, onde quer que
     esteja. O filtro é limpo junto, senão a tela mostraria um trânsito
     que a própria lista diz não existir. */
  for (var j = 0; j < s.total; j++) {
    if (naoDecidido(j)) {
      if (!combina(j)) {
        E.filtro = 'todos';
        E.busca = '';
        if ($('#busca')) $('#busca').value = '';
      }
      irParaTransito(j);
      return;
    }
  }

  recarregarTransito(false).then(function () { mostrar('resumo'); });
}

function abrirMotivos() {
  var t = E.transito;
  var semFoto = !!(t && t.imagens_buscadas && !t.imagens.length);
  E.motivoEscolhido = null;
  $('#campo-outros').hidden = true;
  $('#txt-outros').value = '';
  $('#confirmar-descarte').hidden = true;
  $('#confirmar-descarte').disabled = true;

  $('#opcoes-motivo').innerHTML = CFG.motivos.map(function (m, i) {
    var sug = semFoto && m === CFG.motivo_sem_foto;
    return '<button class="opcao' + (sug ? ' sugerida' : '') + '" data-motivo="'
      + esc(m) + '"><i>' + (i + 1) + '</i>' + esc(m)
      + (sug ? '<span class="sugerido">sugerido</span>' : '') + '</button>';
  }).join('');

  $$('#opcoes-motivo .opcao').forEach(function (b) {
    b.addEventListener('click', function () {
      var m = b.dataset.motivo;
      if (m === CFG.motivo_livre) {
        E.motivoEscolhido = m;
        $$('#opcoes-motivo .opcao').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        $('#campo-outros').hidden = false;
        $('#confirmar-descarte').hidden = false;
        $('#confirmar-descarte').disabled = !$('#txt-outros').value.trim();
        $('#txt-outros').focus();
      } else {
        fecharCortinas();
        decidir('descartado', m, '');
      }
    });
  });
  abrirCortina('cortina-motivos');
}

/* ── ampliação ─────────────────────────────────────────────────────── */
function abrirLente() {
  var lista = fotos();
  if (!lista.length) return;
  var img = lista[E.foto];
  E.lente = { escala: 1, x: 0, y: 0, arrastando: false, ox: 0, oy: 0 };

  var palco = $('#lente-palco');
  palco.innerHTML = '<img src="' + urlImagem(img.codigo) + '" alt="">';
  var el = palco.querySelector('img');
  el.style.filter = 'brightness(' + (E.brilho / 100) + ') contrast('
    + (E.contraste / 100) + ')';
  aplicarLente();

  el.addEventListener('wheel', function (ev) {
    ev.preventDefault();
    var passo = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
    E.lente.escala = Math.min(8, Math.max(1, E.lente.escala * passo));
    if (E.lente.escala === 1) { E.lente.x = 0; E.lente.y = 0; }
    aplicarLente();
  }, { passive: false });

  el.addEventListener('mousedown', function (ev) {
    ev.preventDefault();
    E.lente.arrastando = true;
    E.lente.ox = ev.clientX - E.lente.x;
    E.lente.oy = ev.clientY - E.lente.y;
    el.classList.add('arrastando');
  });
  window.addEventListener('mousemove', moverLente);
  window.addEventListener('mouseup', soltarLente);
  el.addEventListener('dblclick', function () {
    E.lente = { escala: 1, x: 0, y: 0, arrastando: false, ox: 0, oy: 0 };
    aplicarLente();
  });

  $('#lente-legenda').textContent = img.nome + ' · ' + img.arquivo;
  atualizarBotaoLente();
  abrirCortina('cortina-lente');
}

function moverLente(ev) {
  if (!E.lente.arrastando) return;
  E.lente.x = ev.clientX - E.lente.ox;
  E.lente.y = ev.clientY - E.lente.oy;
  aplicarLente();
}
function soltarLente() {
  E.lente.arrastando = false;
  var el = $('#lente-palco img');
  if (el) el.classList.remove('arrastando');
}
function aplicarLente() {
  var el = $('#lente-palco img');
  if (!el) return;
  el.style.transform = 'translate(' + E.lente.x + 'px,' + E.lente.y + 'px) scale('
    + E.lente.escala + ')';
}
function atualizarBotaoLente() {
  var lista = fotos(), t = E.transito;
  if (!lista.length || !t) return;
  var dentro = t.selecionadas.indexOf(lista[E.foto].codigo) >= 0;
  $('#lente-marcar').textContent =
    dentro ? 'Tirar do relatório' : 'Incluir no relatório';
}

/* ── T4 resumo ─────────────────────────────────────────────────────── */
function carregarResumo() {
  $('#aviso-gerado').hidden = true;
  $('#erro-remessa').hidden = true;
  $('#abrir-pasta').hidden = true;
  $('#nota-gerar').hidden = true;
  $('#ir-inicio').hidden = true;
  $('#gerar').hidden = false;

  api('/api/resumo').then(function (r) {
    $('#resumo-sub').textContent = E.estado.modulo_nome + ' · ' + E.estado.arquivo
      + ' · ' + (E.estado.periodo || '') + ' · operador ' + E.estado.operador;
    $('#r-ok').textContent = r.autuados;
    $('#r-no').textContent = r.descartados;
    $('#r-sem').textContent = r.sem_evidencia;
    $('#r-pend').textContent = r.pendentes;
    $('#pasta').value = r.pasta_sugerida;

    var fora = r.pendentes + r.sem_evidencia;
    $('#aviso-pendentes').hidden = !fora;
    if (fora) {
      $('#aviso-pendentes').innerHTML = '<b>' + fora + ' trânsito'
        + (fora > 1 ? 's' : '') + ' fora da remessa.</b> ' + r.pendentes
        + ' sem decisão e ' + r.sem_evidencia + ' sem evidência. '
        + 'Não geram relatório, mas ficam registrados no resumo.';
    }

    var maior = Math.max.apply(null,
      r.por_motivo.map(function (m) { return m.quantidade; }).concat([1]));
    $('#motivos').innerHTML = r.por_motivo.length
      ? r.por_motivo.map(function (m) {
        return '<div class="mot"><span class="barra-mot" style="width:'
          + (16 + 64 * m.quantidade / maior) + 'px"></span><span class="txt">'
          + esc(m.motivo) + '</span><span class="qtd">' + m.quantidade + '</span></div>';
      }).join('')
      : '<span style="font-size:12px;color:var(--suave)">Nenhum descarte nesta sessão.</span>';

    $('#gerar').disabled = !r.autuados;
    $('#gerar').textContent = r.autuados
      ? ('Gerar remessa · ' + r.autuados + ' relatório'
         + (r.autuados > 1 ? 's' : ''))
      : 'Gerar remessa';
  }).catch(function (e) { avisar(e.message); });
}

function gerarRemessa() {
  var btn = $('#gerar');
  btn.disabled = true;
  btn.textContent = 'Gerando…';
  $('#erro-remessa').hidden = true;

  postJson('/api/remessa', { pasta: $('#pasta').value.trim() }).then(function (r) {
    $('#aviso-gerado').hidden = false;
    $('#aviso-gerado').innerHTML = '<b>Remessa gerada.</b> ' + r.relatorios
      + ' relatório' + (r.relatorios > 1 ? 's' : '') + ' em ' + r.paginas
      + ' página' + (r.paginas > 1 ? 's' : '') + ' A4, com ' + r.fotos
      + ' fotos, mais o índice — compactados em <code>' + esc(r.zip) + '</code> ('
      + (r.tamanho_zip / 1048576).toFixed(1) + ' MB) em <code>' + esc(r.pasta)
      + '</code>.'
      + (r.nova_versao ? '<br>A pasta indicada já tinha uma remessa, então '
        + 'esta foi para uma versão nova, ao lado — nada foi sobrescrito.' : '')
      + (r.falhas.length ? '<br><b>' + r.falhas.length + ' falha(s):</b> '
        + r.falhas.map(function (f) { return esc(f.id) + ' — ' + esc(f.erro); }).join('; ')
        : '');
    $('#pasta').value = r.pasta;
    $('#abrir-pasta').hidden = false;
    $('#nota-gerar').hidden = false;
    $('#nota-gerar').innerHTML = 'A remessa está pronta: anexe o '
      + '<code>remessa.zip</code> ao e-mail da PRF. Se precisar corrigir alguma '
      + 'coisa, volte à conferência, ajuste e gere de novo — sai uma versão '
      + 'nova ao lado, e a remessa já enviada fica intacta.';
    btn.hidden = true;
    btn.disabled = false;
    btn.textContent = 'Gerar remessa';
    $('#ir-inicio').hidden = false;
  }).catch(function (e) {
    $('#erro-remessa').hidden = false;
    $('#erro-remessa').textContent = e.message;
    btn.textContent = 'Gerar remessa';
    btn.disabled = false;
  });
}

/* ── cortinas ──────────────────────────────────────────────────────── */
function abrirCortina(id) { $('#' + id).classList.add('on'); }
function fecharCortinas() {
  $$('.cortina').forEach(function (c) { c.classList.remove('on'); });
  window.removeEventListener('mousemove', moverLente);
  window.removeEventListener('mouseup', soltarLente);
}
function algumaCortina() { return $$('.cortina.on').length > 0; }

/* ── ligações ──────────────────────────────────────────────────────── */
function ligar() {
  $('#dropzone').addEventListener('click', pedirArquivo);
  ['dragenter', 'dragover'].forEach(function (ev) {
    $('#dropzone').addEventListener(ev, function (e) {
      e.preventDefault(); this.classList.add('ativo');
    });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    $('#dropzone').addEventListener(ev, function (e) {
      e.preventDefault(); this.classList.remove('ativo');
    });
  });
  $('#dropzone').addEventListener('drop', function (e) {
    var f = e.dataTransfer.files[0];
    if (f) abrirSessao(E.moduloEscolhido, null, f);
  });
  $('#arquivo-input').addEventListener('change', function () {
    if (this.files.length) abrirSessao(E.moduloEscolhido, null, this.files[0]);
  });
  $('#trocar-arquivo').addEventListener('click', resetarCarga);
  $('#iniciar-conferencia').addEventListener('click', function () {
    mostrar('conferencia');
    irParaTransito(E.estado.indice || 0);
  });

  $('#ant').addEventListener('click', function () {
    var i = vizinho(-1);
    if (i >= 0) irParaTransito(i);
  });
  $('#prox').addEventListener('click', function () {
    var i = vizinho(1);
    if (i >= 0) irParaTransito(i);
  });
  var timerBusca = null;
  $('#busca').addEventListener('input', function () {
    var valor = this.value;
    clearTimeout(timerBusca);
    timerBusca = setTimeout(function () {
      E.busca = valor;
      aplicarFiltroDaLista();
    }, 220);
  });
  $('#busca').addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') {
      this.value = ''; E.busca = ''; aplicarFiltroDaLista();
    }
  });

  function saltar() {
    var n = parseInt($('#ir-numero').value, 10);
    if (!n || !E.estado || n < 1 || n > E.estado.total) return;
    irParaTransito(n - 1);
  }
  $('#ir-numero').addEventListener('change', saltar);
  $('#ir-numero').addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); saltar(); }
  });

  $('#foto-ant').addEventListener('click', function () { mudarFoto(-1); });
  $('#foto-prox').addEventListener('click', function () { mudarFoto(1); });

  $('#brilho').addEventListener('input', function () {
    E.brilho = +this.value; aplicarFiltro();
  });
  $('#contraste').addEventListener('input', function () {
    E.contraste = +this.value; aplicarFiltro();
  });
  $('#reset-img').addEventListener('click', function () {
    E.brilho = 100; E.contraste = 100;
    $('#brilho').value = 100; $('#contraste').value = 100;
    aplicarFiltro();
  });
  $('#ampliar').addEventListener('click', abrirLente);
  $('#rebuscar').addEventListener('click', function () {
    postJson('/api/rebuscar', { indice: E.indice }).then(function () {
      E.transito.imagens_buscadas = false;
      desenharConferencia();
      esperarImagens();
    });
  });

  $('#seletor-foto').addEventListener('click', function () {
    var lista = fotos();
    if (lista.length) alternarFoto(lista[E.foto].codigo);
  });
  $('#sel-sugerida').addEventListener('click', function () { acaoSelecao('sugerida'); });
  $('#sel-limpar').addEventListener('click', function () { acaoSelecao('limpar'); });

  $('#btn-autuar').addEventListener('click', autuar);
  $('#btn-descartar').addEventListener('click', abrirMotivos);
  $('#txt-outros').addEventListener('input', function () {
    $('#confirmar-descarte').disabled = !this.value.trim();
  });
  $('#confirmar-descarte').addEventListener('click', function () {
    var txt = $('#txt-outros').value.trim();
    if (!txt) return;
    fecharCortinas();
    decidir('descartado', CFG.motivo_livre, txt);
  });
  $('#lente-marcar').addEventListener('click', function () {
    var lista = fotos();
    if (lista.length) {
      alternarFoto(lista[E.foto].codigo);
      setTimeout(atualizarBotaoLente, 250);
    }
  });

  $('#btn-finalizar').addEventListener('click', function () { mostrar('resumo'); });
  $('#voltar-conferencia').addEventListener('click', function () {
    mostrar('conferencia');
    recarregarTransito(true);
  });
  $('#gerar').addEventListener('click', gerarRemessa);
  $('#ir-inicio').addEventListener('click', function () {
    postJson('/api/encerrar-sessao').then(function (d) {
      E.estado = d.estado;
      E.transito = null;
      desenharModulos();
      mostrar('modulos');
    }).catch(function (e) { avisar(e.message); });
  });
  $('#abrir-pasta').addEventListener('click', function () {
    postJson('/api/abrir-pasta', { pasta: $('#pasta').value.trim() })
      .catch(function (e) { avisar(e.message); });
  });

  $('#btn-trocar-modulo').addEventListener('click', function () {
    var s = E.estado;
    var perigo = s && s.aberta && (s.autuados || s.descartados)
      && !s.pasta_remessa;
    var passo = perigo
      ? perguntar('Trocar de módulo',
          'Há decisões nesta sessão que ainda não viraram remessa. Trocar de '
          + 'módulo encerra a sessão — as decisões ficam salvas e você pode '
          + 'retomar depois.', 'Encerrar e trocar')
      : Promise.resolve(true);
    passo.then(function (ok) {
      if (!ok) return;
      postJson('/api/encerrar-sessao').then(function (d) {
        E.estado = d.estado;
        E.transito = null;
        E.lista = null;
        E.filtro = 'todos';
        E.busca = '';
        desenharModulos();
        mostrar('modulos');
      });
    });
  });

  $('#btn-tema').addEventListener('click', function () {
    var novo = document.documentElement.dataset.tema === 'escuro' ? 'claro' : 'escuro';
    document.documentElement.dataset.tema = novo;
    try { localStorage.setItem('autuacao_tema', novo); } catch (e) { /* ok */ }
  });

  $$('[data-fecha]').forEach(function (b) {
    b.addEventListener('click', fecharCortinas);
  });
  $$('.cortina').forEach(function (c) {
    c.addEventListener('click', function (ev) { if (ev.target === c) fecharCortinas(); });
  });

  document.addEventListener('keydown', aoTeclar);
}

function aplicarFiltro() {
  var f = 'brightness(' + (E.brilho / 100) + ') contrast(' + (E.contraste / 100) + ')';
  var a = $('#palco img'); if (a) a.style.filter = f;
  var b = $('#lente-palco img'); if (b) b.style.filter = f;
}

/* ── teclado ───────────────────────────────────────────────────────────
   Só campos de digitação de texto capturam os atalhos. Brilho e contraste
   são input[type=range]: se bloqueassem, mexer no brilho — justamente o
   gesto que antecede olhar a próxima foto — mataria todos os atalhos.
   Enter e Espaço são a exceção: pertencem ao botão que estiver focado.  */
function aoTeclar(ev) {
  if (ev.key === 'Escape') { fecharCortinas(); return; }

  var naLente = $('#cortina-lente').classList.contains('on');
  var alvo = ev.target || document.body;
  var tag = alvo.tagName || '';
  var tipo = String(alvo.type || '').toLowerCase();
  var textual = tag === 'TEXTAREA'
    || (tag === 'INPUT'
      && ['text', 'search', 'url', 'email', 'password', 'number', 'tel'].indexOf(tipo) >= 0);
  if (textual) return;

  if (naLente) {
    if (ev.key === ' ') {
      ev.preventDefault();
      $('#lente-marcar').click();
    } else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowRight') {
      ev.preventDefault();
      mudarFoto(ev.key === 'ArrowLeft' ? -1 : 1);
      fecharCortinas();
      abrirLente();
    }
    return;
  }

  if (algumaCortina() || E.tela !== 'conferencia') return;
  var emControle = (tag === 'BUTTON' || tag === 'A');
  var lista = fotos();

  if (ev.key === 'Enter') {
    if (emControle) return;
    ev.preventDefault();
    autuar();
  } else if (ev.key === 'Backspace') {
    ev.preventDefault();
    abrirMotivos();
  } else if (ev.key === ' ') {
    if (emControle) return;
    ev.preventDefault();
    if (lista.length) alternarFoto(lista[E.foto].codigo);
  } else if (ev.key === 'ArrowLeft') {
    ev.preventDefault(); mudarFoto(-1);
  } else if (ev.key === 'ArrowRight') {
    ev.preventDefault(); mudarFoto(1);
  } else if (ev.key === 'ArrowUp' || ev.key === 'ArrowDown') {
    ev.preventDefault();
    if (!lista.length) return;
    var presentes = [];
    lista.forEach(function (i) {
      if (presentes.indexOf(i.angulo) < 0) presentes.push(i.angulo);
    });
    var atual = presentes.indexOf(lista[E.foto].angulo);
    var passo = (ev.key === 'ArrowUp') ? -1 : 1;
    irParaAngulo(presentes[(atual + passo + presentes.length) % presentes.length]);
  } else if (ev.key === 'PageUp') {
    ev.preventDefault(); $('#ant').click();
  } else if (ev.key === 'PageDown') {
    ev.preventDefault(); $('#prox').click();
  } else if (ev.key === 'f' || ev.key === 'F') {
    ev.preventDefault(); abrirLente();
  } else if ('1234'.indexOf(ev.key) >= 0 && E.transito) {
    ev.preventDefault();
    irParaAngulo(E.transito.ordem_angulos[+ev.key - 1]);
  }
}

/* ── arranque ──────────────────────────────────────────────────────── */
function iniciar() {
  try {
    var tema = localStorage.getItem('autuacao_tema');
    if (tema) document.documentElement.dataset.tema = tema;
  } catch (e) { /* ok */ }

  api('/api/inicio').then(function (d) {
    CFG = d;
    E.estado = d.estado;
    $('#versao').textContent = d.versao;
    ligar();
    desenharModulos();

    if (d.estado && d.estado.aberta) {
      E.moduloEscolhido = d.estado.modulo;
      $('#nome-modulo').textContent = d.estado.modulo_nome;
      $('#marca-modulo').className = 'marca-pista mp-' + d.estado.modulo;
      mostrar('conferencia');
      carregarLista().then(function () {
        irParaTransito(d.estado.indice || 0);
      });
    } else {
      mostrar('modulos');
    }
  }).catch(function (e) {
    document.body.innerHTML = '<div class="carregando">Não consegui falar com o '
      + 'servidor local: ' + esc(e.message) + '</div>';
  });
}

document.addEventListener('DOMContentLoaded', iniciar);

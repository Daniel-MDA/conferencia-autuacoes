# -*- mode: python ; coding: utf-8 -*-
"""
Empacotamento em executável único (RNF-01).

    pyinstaller ConferenciaAutuacoes.spec --noconfirm

Entregue a pasta `dist` inteira. Na máquina do operador não precisa de
Python nem de Excel: duplo clique no .exe.

A LOGO fica FORA do executável, ao lado dele, para poder ser trocada sem
recompilar. Todo o resto — interface, fontes do reportlab, o núcleo — vai
embutido.
"""

import os
import sys

# Impressao digital do codigo-fonte, calculada agora e gravada dentro do
# pacote. E o que permite ao verificar_build.py provar que o .exe gerado e
# este codigo, e nao uma sobra de cache com data de hoje.
sys.path.insert(0, os.path.abspath(SPECPATH))
from autuacao.impressao import NOME_EMBUTIDO, calcular

_impressao = calcular(os.path.abspath(SPECPATH))
_pasta = os.path.join(SPECPATH, "build")
os.makedirs(_pasta, exist_ok=True)
_arquivo_impressao = os.path.join(_pasta, NOME_EMBUTIDO)
with open(_arquivo_impressao, "w", encoding="utf-8") as _f:
    _f.write(_impressao)
print("impressao do codigo-fonte:", _impressao)

bloco_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # a interface: index.html, app.js, style.css
        ('autuacao/web', 'web'),
        # a impressao digital do codigo que gerou este pacote
        (_arquivo_impressao, '.'),
    ],
    hiddenimports=[
        # backend do pywebview no Windows
        'webview.platforms.edgechromium',
        'clr_loader',
        'pythonnet',
        # modo de reserva quando o WebView2 falta (R-02)
        'tkinter',
        # usados por reflexão
        'openpyxl.cell._writer',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ferramentas de desenvolvimento que nao vao para o operador.
        # NAO exclua 'bottle': o webview/http.py o importa incondicionalmente,
        # e sem ele o `import webview` quebra e a aplicacao cai calada para o
        # navegador. Foi exatamente o que aconteceu na primeira build.
        'pymupdf', 'fitz',
        'matplotlib', 'numpy', 'pandas', 'pytest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ConferenciaAutuacoes',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # janela nativa de verdade: sem console preto atrás (RNF-02).
    # Quando o WebView2 falta, quem segura a aplicação de pé é a janelinha
    # de espera do tkinter — ver autuacao/janela.py.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

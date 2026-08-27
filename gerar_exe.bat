@echo off
chcp 65001 >nul
setlocal

echo.
echo   Conferencia de Autuacoes - geracao do executavel
echo   -----------------------------------------------
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo   Python nao encontrado no PATH. Instale o Python 3.10 ou superior.
  echo.
  pause
  exit /b 1
)

rem -- [1/5] o programa nao pode estar rodando ---------------------------
rem O PyInstaller grava por cima de dist\ConferenciaAutuacoes.exe. Se uma
rem copia estiver aberta, o Windows nega o acesso e a build morre com uma
rem mensagem que nao explica nada.
echo   [1/5] Verificando se o programa esta aberto...
tasklist /FI "IMAGENAME eq ConferenciaAutuacoes.exe" 2>nul | find /I "ConferenciaAutuacoes.exe" >nul
if not errorlevel 1 (
  echo         O programa esta aberto. Fechando antes de gerar...
  taskkill /F /IM ConferenciaAutuacoes.exe >nul 2>&1
  timeout /t 2 /nobreak >nul
)
echo         ok

rem -- [2/5] dependencias -----------------------------------------------
echo   [2/5] Instalando dependencias...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo   Falha ao instalar as dependencias.
  echo.
  pause
  exit /b 1
)
echo         ok

rem -- [3/5] empacotar --------------------------------------------------
rem --clean apaga o cache do PyInstaller: sem isso uma build pode reusar
rem pedacos da anterior e sair com codigo velho dentro.
echo   [3/5] Empacotando...
python -m PyInstaller ConferenciaAutuacoes.spec --noconfirm --clean
if errorlevel 1 (
  echo.
  echo   Falha no empacotamento.
  echo.
  pause
  exit /b 1
)
echo         ok

rem -- [4/5] a logo -----------------------------------------------------
echo   [4/5] Copiando a logo para o lado do executavel...
if exist logo.png (
  copy /y logo.png dist\logo.png >nul
  echo         logo.png copiada.
) else (
  echo         AVISO: logo.png nao existe na raiz do projeto. O relatorio vai
  echo         sair com o nome da concessionaria escrito no lugar da marca.
)

rem -- [5/5] conferir se o que saiu funciona ----------------------------
rem Empacotar sem erro nao garante que o programa abre: a primeira build
rem deste projeto terminou "com sucesso" e mesmo assim caia para o
rem navegador, porque faltava uma dependencia dentro do pacote.
echo   [5/5] Testando o executavel gerado...
python verificar_build.py
if errorlevel 1 (
  echo.
  echo   ATENCAO: o executavel foi gerado, mas nao passou na verificacao.
  echo   Leia as falhas acima antes de entregar.
  echo.
  pause
  exit /b 1
)

echo.
echo   Pronto. Entregue a pasta dist inteira:
echo       dist\ConferenciaAutuacoes.exe
echo       dist\logo.png
echo.
pause
endlocal

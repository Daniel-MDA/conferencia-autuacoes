@echo off
chcp 65001 >nul
echo   Modo demonstracao: imagens sinteticas, sem acessar o servidor.
python main.py --demo %*

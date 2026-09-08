@echo off
rem =====================================================================
rem   COMPTA LMNP - LANCEUR WINDOWS
rem   Double-cliquez sur ce fichier.
rem
rem   MAINTENANCE : ce fichier doit rester en ASCII PUR (aucun accent,
rem   aucun caractere de dessin) et en fins de ligne CRLF. cmd.exe lit un
rem   .bat octet par octet : un caractere accentue ou une fin de ligne
rem   Unix decale sa lecture et il avale le debut des lignes suivantes.
rem   Un test automatique verifie ces deux proprietes a chaque livraison.
rem
rem   Le nom du fichier porte -Windows : sous Windows les extensions sont
rem   masquees par defaut, et le lanceur Linux (.sh) s'affichait sous un
rem   nom IDENTIQUE juste a cote. Deux fichiers jumeaux, un seul qui
rem   marche : constate en usage reel.
rem
rem   Prerequis (une seule fois) : installer Python 3 depuis
rem   https://www.python.org/downloads/ en COCHANT la case
rem   "Add python.exe to PATH" pendant l'installation.
rem =====================================================================
setlocal
cd /d "%~dp0"
title Compta LMNP

echo ==========================================
echo    Compta LMNP - demarrage
echo ==========================================

rem --- 1. Python 3 disponible ? ---------------------------------------
rem Le lanceur py est prefere : il trouve Python meme absent du PATH.
rem On EXECUTE la commande au lieu de tester sa seule presence, car
rem Windows 10 fournit un faux python.exe qui ouvre le Microsoft Store.
set "PYCMD="
py -3 --version >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
    python --version >nul 2>nul && set "PYCMD=python"
)
if not defined PYCMD goto :pas_de_python
for /f "tokens=*" %%v in ('%PYCMD% --version 2^>^&1') do set "PYVER=%%v"
echo   [OK] %PYVER% detecte.

rem --- 2. Environnement local (.venv) ----------------------------------
rem On teste que l'environnement FONCTIONNE, pas qu'il existe : une
rem creation interrompue laisse un .venv incomplet, et un simple test de
rem presence le croit pret (constate sous Linux, meme piege ici).
".venv\Scripts\python.exe" -m pip --version >nul 2>nul && goto :venv_ok
if exist ".venv" (
    echo   [!!] Environnement local incomplet - reconstruction.
    rmdir /s /q ".venv"
)
echo   [..] Premier lancement : creation de l'environnement local...
echo        (cette etape dure 1 a 3 minutes, ne fermez pas la fenetre)
%PYCMD% -m venv .venv
if errorlevel 1 goto :echec_venv
".venv\Scripts\python.exe" -m pip --version >nul 2>nul || ".venv\Scripts\python.exe" -m ensurepip --upgrade >nul 2>nul
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
echo   [..] Installation de Flask...
".venv\Scripts\python.exe" -m pip install --quiet flask
if errorlevel 1 goto :echec_pip
rem reportlab sert uniquement a l'export PDF : son absence n'empeche
rem pas le logiciel de fonctionner (l'application le detecte et le dit).
echo   [..] Installation de reportlab (export PDF, facultatif)...
".venv\Scripts\python.exe" -m pip install --quiet reportlab
if errorlevel 1 echo   [!!] reportlab non installe - tout fonctionne sauf
if errorlevel 1 echo        l'export PDF de la liasse (l'affichage a l'ecran
if errorlevel 1 echo        et l'impression navigateur restent disponibles).
:venv_ok
set "PY=.venv\Scripts\python.exe"
"%PY%" -c "import flask" >nul 2>nul || "%PY%" -m pip install --quiet flask
echo   [OK] Environnement local pret.

rem --- 3. Raccourci sur le Bureau (une seule fois) ----------------------
rem Sans raccourci, il faut retrouver le dossier a chaque fois. Le
rem marqueur evite de le recreer si l'utilisateur l'a supprime volontairement.
if exist ".raccourci_bureau" goto :raccourci_ok
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; $c = $w.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Compta LMNP.lnk')); $c.TargetPath = '%~f0'; $c.WorkingDirectory = '%~dp0'; $c.Description = 'Comptabilite LMNP au reel'; $c.Save()" >nul 2>nul
if exist "%USERPROFILE%\Desktop\Compta LMNP.lnk" echo   [OK] Raccourci "Compta LMNP" cree sur le Bureau.
echo marqueur > ".raccourci_bureau"
:raccourci_ok

rem --- 4. Demarrage + navigateur ---------------------------------------
set "URL=http://localhost:5000"
echo.
echo   [OK] Demarrage de Compta LMNP  -^>  %URL%
echo        Pas de cadenas dans la barre d'adresse, et c'est normal :
echo        vos donnees ne quittent pas cet ordinateur et ne traversent
echo        aucun reseau. (HTTPS local possible : voir INSTALLATION.md.)
echo        Pour arreter : Ctrl+C ou fermer cette fenetre.
echo.
echo   Si aucune page ne s'ouvre, collez cette adresse dans votre
echo   navigateur :   %URL%
echo.
rem Le navigateur ne doit s'ouvrir QU'APRES le demarrage du serveur :
rem sinon la page s'affiche sur un port encore muet (site inaccessible).
start "" /b "%PY%" ouvrir_navigateur.py "%URL%"
"%PY%" app.py
pause
exit /b 0

:pas_de_python
echo   [XX] Python 3 introuvable.
echo.
echo        Installez-le depuis https://www.python.org/downloads/
echo        et COCHEZ "Add python.exe to PATH" pendant l installation,
echo        puis relancez ce fichier.
echo.
echo        Si Python est deja installe et que ce message apparait,
echo        c est que Windows ne le trouve pas : reinstallez-le en
echo        cochant bien la case, ou lancez l installation avec
echo        l option "Install launcher for all users".
pause
exit /b 1

:echec_venv
echo   [XX] Echec de creation de l environnement local (.venv).
echo        Verifiez que le dossier n est pas en lecture seule
echo        (evitez Program Files) ni synchronise par OneDrive.
pause
exit /b 1

:echec_pip
echo   [XX] Echec d installation de Flask.
echo        Une connexion internet est requise au premier lancement.
echo        Si vous utilisez une version tres recente de Python et que
echo        l installation echoue, installez Python 3.12 ou 3.13 :
echo        certaines dependances n ont pas encore de version prete
echo        pour les toutes dernieres moutures.
pause
exit /b 1

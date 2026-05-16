@echo off
echo ========================================
echo Configurador do App Android
echo ========================================
echo.

REM Obter IP local
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP: =%

echo IP detectado: %IP%
echo.

REM Perguntar se quer usar este IP
set /p CONFIRM="Usar este IP no app? (S/N): "
if /i "%CONFIRM%"=="N" (
    set /p IP="Digite o IP do servidor: "
)

REM Atualizar MainActivity.java
set JAVA_FILE=app\src\main\java\com\auditoria\app\MainActivity.java
powershell -Command "(gc '%JAVA_FILE%') -replace 'private static final String SERVER_URL = .*;', 'private static final String SERVER_URL = \"http://%IP%:8501\";' | Out-File -encoding ASCII '%JAVA_FILE%'"

echo.
echo Configuracao atualizada!
echo URL: http://%IP%:8501
echo.
echo Agora abra o projeto no Android Studio e compile.
pause

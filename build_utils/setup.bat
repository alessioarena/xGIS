@ECHO OFF

SETLOCAL ENABLEDELAYEDEXPANSION
SET ERRORLEVEL=

CD %~dp0
if "%PYTHONEMBEDDED%" == "1" (
    SET EXECUTABLE="python_embedded/python.exe"
) else if "%ARCGISSUPPORT%"=="1" (
    FOR /F "tokens=* USEBACKQ" %%F IN (`python.exe setup_external_libs.py --find_arcgis_env --major 10 --bit 64 `) DO ( SET EXECUTABLE="%%F" )
) else (
    if "%PYTHONVERSION%"=="2" (
        FOR /F "tokens=* USEBACKQ" %%F IN (`python.exe setup_external_libs.py --find_qgis_env --major 3 --bit 64 --python_major 2`) DO ( SET EXECUTABLE="%%F" )
    ) else (
        FOR /F "tokens=* USEBACKQ" %%F IN (`python.exe setup_external_libs.py --find_qgis_env --major 3 --bit 64 --python_major 3`) DO ( SET EXECUTABLE="%%F" )
    )
)

REM FOR /L %%i IN (6,-1,1) DO (
REM     IF EXIST C:\Python27\ArcGISx6410.%%i%\python.exe (
REM         SET EXECUTABLE=C:\Python27\ArcGISx6410.%%i%\python.exe
REM     )
REM )


if defined EXECUTABLE (
    @ECHO Installing additional libraries. This may take some times depending on your system
    @ECHO Running %EXECUTABLE% setup_external_libs.py
    %EXECUTABLE% setup_external_libs.py --yaml requirements.yml
    if ERRORLEVEL 1 (
        @ECHO.
        @ECHO Installation Failed!
        @PAUSE
    ) else (
        @ECHO.
        if "%QGISSUPPORT%"=="1" (
            pushd ..
            @ECHO Setting up the QGIS_PLUGINPATH to !CD!
            setx QGIS_PLUGINPATH !CD!
            popd
        )
        @ECHO Installation Successful!
        if NOT "%SPLASHSCREEN%"=="None" (
            start %SPLASHSCREEN%
        )
        
        @TIMEOUT 30
    )
    EXIT /b !ERRORLEVEL!
) else (
    @ECHO.
    if "%ARCGISSUPPORT%"=="1" (
        @ECHO Could not find a valid ArcGIS 10.x 64bit Python environment
    ) else (
        @ECHO Could not find a valid QGIS 3.x 64bit Python environment
    )
    @ECHO Could not complete the installation
    @PAUSE
    EXIT /b 2
)
@ECHO OFF

SETLOCAL ENABLEDELAYEDEXPANSION
SET ERRORLEVEL=
CD %~dp0


@REM Check that we have MSBuild Installed
SET MSBUILD_EXE=
for /f "usebackq tokens=*" %%i in (`vswhere -latest -products * -requires Microsoft.Component.MSBuild Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find MSBuild\**\Bin\MSBuild.exe`) do (
    SET "MSBUILD_EXE=%%i"
)
if "%MSBUILD_EXE%" == "" (
    @ECHO MS Visual Studio Build Tools are missing from your system. Please install them and try again
    @PAUSE
    EXIT /b 2
) else (
    @ECHO Found a MS Visual Studio Build Tools version at "%MSBUILD_EXE%"
    SET "PATH=!PATH!;!MSBUILD_EXE:~0,-12!;!MSBUILD_EXE:~0,-12!\amd64"
)

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

if defined EXECUTABLE (
    @ECHO Installing additional libraries. This may take some times depending on your system
    @ECHO Running %EXECUTABLE% setup_external_libs.py
    IF "%PYTHONEMBEDDED%" == "1" (
        %EXECUTABLE% setup_external_libs.py --yaml requirements.yml -v --target False
    ) ELSE (
        %EXECUTABLE% setup_external_libs.py --yaml requirements.yml -v
    )
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
        if NOT "%SPLASHSCREEN%"=="" (
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
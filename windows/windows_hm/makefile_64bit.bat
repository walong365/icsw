SET HM_VERSION=3.0.11
SET HM_PLATFORM=win64
SET PCIUTILS_VERSION=3.4.0
SET WINPYTH_MAJOR=6
SET WINPYTH_MINOR=0
SET WINPYTH_MINORFIX=1
SET WIX_BIN_PATH=C:\Program Files (x86)\WiX Toolset v3.10\bin\

:: Fetch pciutils and move into script directory
..\windows_common_files\bin\wget -nc https://eternallybored.org/misc/pciutils/releases/pciutils-%PCIUTILS_VERSION%-win64.zip
..\windows_common_files\bin\7z -o.\tmp\ x pciutils-%PCIUTILS_VERSION%-win64.zip

:: Fetch full and zero version of (portable) python
..\windows_common_files\bin\wget --no-check-certificate -nc https://sourceforge.net/projects/winpython/files/WinPython_3.%WINPYTH_MAJOR%/3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%/WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%Zero.exe
..\windows_common_files\bin\7z -o.\tmp\zero x WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%Zero.exe

:: install missing/needed modules
MOVE .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64 .\host_monitor_windows
.\host_monitor_windows\python.exe -m pip install --upgrade pip
.\host_monitor_windows\python.exe -m pip install lxml==3.7.2
.\host_monitor_windows\python.exe -m pip install netifaces==0.10.5
.\host_monitor_windows\python.exe -m pip install setproctitle==1.1.10
.\host_monitor_windows\python.exe -m pip install pyzmq==16.0.2
.\host_monitor_windows\python.exe -m pip install psutil==5.1.3
.\host_monitor_windows\python.exe -m pip install wmi
.\host_monitor_windows\python.exe -m pip install pypiwin32

XCOPY .\inflection.py .\host_monitor_windows\Lib\site-packages\
XCOPY .\syslog.py .\host_monitor_windows\Lib\site-packages\
XCOPY .\service_manager.py .\host_monitor_windows\

MKDIR .\host_monitor_windows\Lib\site-packages\initat
MKDIR .\host_monitor_windows\Lib\site-packages\initat\host_monitoring
MKDIR .\host_monitor_windows\Lib\site-packages\initat\tools
MKDIR .\host_monitor_windows\Lib\site-packages\initat\icsw
MKDIR .\host_monitor_windows\Lib\site-packages\opt
XCOPY ..\initat\icsw .\host_monitor_windows\Lib\site-packages\initat\icsw\ /E
XCOPY ..\initat\host_monitoring .\host_monitor_windows\Lib\site-packages\initat\host_monitoring\ /E
XCOPY ..\initat\logging_server .\host_monitor_windows\Lib\site-packages\initat\logging_server\ /E
XCOPY ..\initat\tools .\host_monitor_windows\Lib\site-packages\initat\tools\ /E
XCOPY ..\initat\*.py .\host_monitor_windows\Lib\site-packages\initat\
XCOPY ..\opt .\host_monitor_windows\Lib\site-packages\opt /E
COPY .\host_monitor_windows\Lib\site-packages\opt\cluster\etc\cstores.d\client_sample_config.xml .\host_monitor_windows\Lib\site-packages\opt\cluster\etc\cstores.d\client_config.xml

RMDIR /s /q .\host_monitor_windows\tcl
RMDIR /s /q .\host_monitor_windows\Tools
RMDIR /s /q .\host_monitor_windows\Doc

XCOPY ..\windows_common_files\bin\win64\nssm.exe .\host_monitor_windows\
XCOPY ..\windows_common_files\bin\dmidecode212.exe .\host_monitor_windows\
MOVE .\tmp\pciutils-%PCIUTILS_VERSION%-win64 .\host_monitor_windows\pciutils
type nul > .\host_monitor_windows\hm_icsw_w64

host_monitor_windows\python -c "import tarfile; tar = tarfile.open(name='ICSW_Windows_Client-%HM_VERSION%-%HM_PLATFORM%.tar.xz', mode='w:xz'); tar.add('host_monitor_windows', arcname=''); tar.close();"

SET hm_path=host_monitor_windows
"%WIX_BIN_PATH%heat.exe" dir host_monitor_windows -cg HostmonitorFiles -dr INSTALLDIR -gg -scom -sreg -sfrag -srd -var env.hm_path -out "Components.wxs"
"%WIX_BIN_PATH%candle.exe" ICSW_Windows_Client.wxs
"%WIX_BIN_PATH%candle.exe" Components.wxs
"%WIX_BIN_PATH%light.exe" -ext WixUIExtension -dWixUILicenseRtf=..\windows_common_files\legal_text.rtf -dWixUIBannerBmp=..\windows_common_files\WixUIBannerBmp.bmp -dWixUIExclamationIco=..\windows_common_files\WixUIExclamationIco.ico -dWixUIDialogBmp=..\windows_common_files\WixUIDialogBmp.bmp ICSW_Windows_Client.wixobj Components.wixobj -o ICSW_Windows_Client-%HM_VERSION%-%HM_PLATFORM%.msi
:: Cleanup temporary files
RMDIR /s /q .\tmp
RMDIR /s /q .\host_monitor_windows
DEL .\Components.wixobj
DEL .\Components.wxs
DEL .\ICSW_Windows_Client.wixobj
DEL .\ICSW_Windows_Client-%HM_VERSION%-%HM_PLATFORM%.wixpdb

@pause

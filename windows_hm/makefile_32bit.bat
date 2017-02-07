SET PCIUTILS_VERSION=3.4.0
SET WINPYTH_MAJOR=6
SET WINPYTH_MINOR=0
SET WINPYTH_MINORFIX=1
SET WIX_BIN_PATH=C:\Program Files (x86)\WiX Toolset v3.10\bin\

:: Fetch pciutils and move into script directory
bin\wget --no-check-certificate -nc https://eternallybored.org/misc/pciutils/releases/pciutils-%PCIUTILS_VERSION%-win32.zip
bin\7z -o.\tmp\ x pciutils-%PCIUTILS_VERSION%-win32.zip

:: Fetch full and zero version of (portable) python
bin\wget --no-check-certificate -nc https://sourceforge.net/projects/winpython/files/WinPython_3.%WINPYTH_MAJOR%/3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%/WinPython-32bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%Zero.exe
bin\7z -o.\tmp\zero x WinPython-32bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%Zero.exe

:: install missing/needed modules
MOVE .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR% .\host_monitor_windows
.\host_monitor_windows\python.exe -m pip install --upgrade pip
.\host_monitor_windows\python.exe -m pip install lxml
.\host_monitor_windows\python.exe -m pip install python-memcached
.\host_monitor_windows\python.exe -m pip install netifaces
.\host_monitor_windows\python.exe -m pip install setproctitle
.\host_monitor_windows\python.exe -m pip install zmq
.\host_monitor_windows\python.exe -m pip install psutil
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
XCOPY ..\initat\host_monitoring .\host_monitor_windows\Lib\site-packages\initat\logging_server\ /E
XCOPY ..\initat\tools .\host_monitor_windows\Lib\site-packages\initat\tools\ /E
XCOPY ..\initat\*.py .\host_monitor_windows\Lib\site-packages\initat\
XCOPY ..\opt .\host_monitor_windows\Lib\site-packages\opt /E
COPY .\host_monitor_windows\Lib\site-packages\opt\cluster\etc\cstores.d\client_sample_config.xml .\host_monitor_windows\Lib\site-packages\opt\cluster\etc\cstores.d\client_config.xml

RMDIR /s /q .\host_monitor_windows\tcl
RMDIR /s /q .\host_monitor_windows\Tools
RMDIR /s /q .\host_monitor_windows\Doc

XCOPY .\bin\win32\nssm.exe .\host_monitor_windows\
XCOPY .\bin\dmidecode212.exe .\host_monitor_windows\
MOVE .\tmp\pciutils-%PCIUTILS_VERSION%-win32 .\host_monitor_windows\pciutils

SET hm_path=host_monitor_windows
"%WIX_BIN_PATH%heat.exe" dir host_monitor_windows -cg HostmonitorFiles -dr INSTALLDIR -gg -scom -sreg -sfrag -srd -var env.hm_path -out "Components.wxs"
"%WIX_BIN_PATH%candle.exe" ICSW_Windows_Client.wxs
"%WIX_BIN_PATH%candle.exe" Components.wxs
"%WIX_BIN_PATH%light.exe" -ext WixUIExtension -dWixUILicenseRtf=legal_text.rtf -dWixUIBannerBmp=WixUIBannerBmp.bmp -dWixUIExclamationIco=WixUIExclamationIco.ico -dWixUIDialogBmp=WixUIDialogBmp.bmp ICSW_Windows_Client.wixobj Components.wixobj -o ICSW_Windows_Client.msi

:: Cleanup temporary files
RMDIR /s /q .\tmp
RMDIR /s /q .\host_monitor_windows
DEL .\Components.wixobj
DEL .\Components.wxs
DEL .\ICSW_Windows_Client.wixobj
DEL .\ICSW_Windows_Client.wixpdb

@pause

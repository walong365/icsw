SET PCIUTILS_VERSION=3.4.0
SET WINPYTH_MAJOR=5
SET WINPYTH_MINOR=2
SET WINPYTH_MINORFIX=3
SET WIX_BIN_PATH=C:\Program Files (x86)\WiX Toolset v3.10\bin\

:: Fetch pciutils and move into script directory
:: bin\wget -nc https://eternallybored.org/misc/pciutils/releases/pciutils-%PCIUTILS_VERSION%-win32.zip
:: bin\7z -o.\tmp\ x pciutils-%PCIUTILS_VERSION%-win32.zip

:: Fetch full and zero version of (portable) python
bin\wget -nc https://sourceforge.net/projects/winpython/files/WinPython_3.%WINPYTH_MAJOR%/3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%/WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%.exe
bin\wget -nc https://sourceforge.net/projects/winpython/files/WinPython_3.%WINPYTH_MAJOR%/3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%/WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%Zero.exe


bin\7z -o.\tmp\zero x WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%Zero.exe
bin\7z -o.\tmp\full x WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%.exe


COPY .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\pywintypes3%WINPYTH_MAJOR%.dll  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\
COPY .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\pythoncom3%WINPYTH_MAJOR%.dll  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\

COPY .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\PyWin32.chm  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
COPY .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pywin32.pth  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
COPY .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pywin32.version.txt  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
COPY .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pythoncom.py  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\


MOVE .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pythonwin  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
MOVE .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pywin32_system32  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
MOVE .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\win32  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
MOVE .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\win32com  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
MOVE .\tmp\full\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\win32comext  .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\


MOVE .\tmp\zero\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64 .\host_monitor_windows
.\host_monitor_windows\python.exe -m pip install --upgrade pip
.\host_monitor_windows\python.exe -m pip install lxml
.\host_monitor_windows\python.exe -m pip install python-memcached
.\host_monitor_windows\python.exe -m pip install netifaces
.\host_monitor_windows\python.exe -m pip install setproctitle
.\host_monitor_windows\python.exe -m pip install zmq
.\host_monitor_windows\python.exe -m pip install psutil

XCOPY .\syslog.py .\host_monitor_windows\Lib\site-packages\

MKDIR .\host_monitor_windows\Lib\site-packages\initat
MKDIR .\host_monitor_windows\Lib\site-packages\initat\host_monitoring
MKDIR .\host_monitor_windows\Lib\site-packages\initat\tools
MKDIR .\host_monitor_windows\Lib\site-packages\initat\icsw
MKDIR .\host_monitor_windows\Lib\site-packages\opt
XCOPY ..\initat\icsw .\host_monitor_windows\Lib\site-packages\initat\icsw\ /E
XCOPY ..\initat\host_monitoring .\host_monitor_windows\Lib\site-packages\initat\host_monitoring\ /E
XCOPY ..\initat\tools .\host_monitor_windows\Lib\site-packages\initat\tools\ /E
XCOPY ..\initat\*.py .\host_monitor_windows\Lib\site-packages\initat\
XCOPY ..\opt .\host_monitor_windows\Lib\site-packages\opt /E 

RMDIR /s /q .\host_monitor_windows\tcl
RMDIR /s /q .\host_monitor_windows\Tools
RMDIR /s /q .\host_monitor_windows\Doc

XCOPY .\bin\nssm.exe .\host_monitor_windows\

:: XCOPY .\nscp\python\pywintypes3%WINPYTH_MAJOR%.dll .\nscp\
:: XCOPY .\scripts\* .\nscp\scripts\python\
:: XCOPY .\scripts\finalize-install.py .\nscp\
:: XCOPY .\nsclient.ini .\nscp\

:: MOVE .\tmp\pciutils-%PCIUTILS_VERSION%-win32 .\nscp\scripts\python\pciutils

MOVE .\host_monitor_windows .\nscp

SET nscp_path=nscp
"%WIX_BIN_PATH%heat.exe" dir nscp -cg NscpFiles -dr INSTALLDIR -gg -scom -sreg -sfrag -srd -var env.nscp_path -out "Components.wxs"
"%WIX_BIN_PATH%candle.exe" ICSW_Windows_Client.wxs
"%WIX_BIN_PATH%candle.exe" Components.wxs
::"%WIX_BIN_PATH%candle.exe" HostEditingDlg.wxs
"%WIX_BIN_PATH%light.exe" -ext WixUIExtension -dWixUILicenseRtf=legal_text.rtf -dWixUIBannerBmp=WixUIBannerBmp.bmp -dWixUIExclamationIco=WixUIExclamationIco.ico -dWixUIDialogBmp=WixUIDialogBmp.bmp ICSW_Windows_Client.wixobj Components.wixobj -o ICSW_Windows_Client.msi

:: Cleanup temporary files
RMDIR /s /q .\tmp
RMDIR /s /q .\nscp
DEL .\Components.wixobj
DEL .\Components.wxs
DEL .\ICSW_Windows_Client.wixobj
DEL .\ICSW_Windows_Client.wixpdb
:: DEL .\HostEditingDlg.wixobj

@pause

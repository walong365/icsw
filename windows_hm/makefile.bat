SET PCIUTILS_VERSION=3.4.0
SET NSCP_VERSION=0.4.4.23
SET WINPYTH_MAJOR=5
SET WINPYTH_MINOR=1
SET WINPYTH_MINORFIX=3
SET WIX_BIN_PATH=C:\Program Files (x86)\WiX Toolset v3.10\bin\

:: Fetch pciutils and move into script directory
bin\wget -nc https://eternallybored.org/misc/pciutils/releases/pciutils-%PCIUTILS_VERSION%-win32.zip
bin\7z -o.\tmp\ x pciutils-%PCIUTILS_VERSION%-win32.zip

bin\wget -nc https://github.com/mickem/nscp/releases/download/%NSCP_VERSION%/nscp-%NSCP_VERSION%-Win32.zip
bin\7z -o.\nscp x nscp-%NSCP_VERSION%-Win32.zip

bin\wget -nc https://sourceforge.net/projects/winpython/files/WinPython_3.%WINPYTH_MAJOR%/3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%/WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%.exe
bin\wget -nc https://sourceforge.net/projects/winpython/files/WinPython_3.%WINPYTH_MAJOR%/3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%/WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%Zero.exe

bin\7z -o.\tmp\zero x WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%Zero.exe
bin\7z -o.\tmp\full x WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%.exe


COPY .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\pywintypes3%WINPYTH_MAJOR%.dll  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\
COPY .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\pythoncom3%WINPYTH_MAJOR%.dll  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\

COPY .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\PyWin32.chm  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
COPY .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pywin32.pth  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
COPY .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pywin32.version.txt  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
COPY .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pythoncom.py  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\


MOVE .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pythonwin  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
MOVE .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pywin32_system32  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
MOVE .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\pywin32-220.dist-info  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
MOVE .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\win32  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
MOVE .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\win32com  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\
MOVE .\tmp\full\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\win32comext  .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64\Lib\site-packages\


MOVE .\tmp\zero\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64 .\nscp\python
COPY .\nscp\python\pywintypes3%WINPYTH_MAJOR%.dll .\nscp\
COPY .\scripts\* .\nscp\scripts\python\
COPY .\scripts\finalize-install.py .\nscp\

RENAME .\tmp\pciutils-%PCIUTILS_VERSION%-win32 .\tmp\pciutils
MOVE .\tmp\pciutils .\nscp\scripts\python\

SET nscp_path=nscp
"%WIX_BIN_PATH%heat.exe" dir nscp -cg NscpFiles -dr INSTALLDIR -gg -scom -sreg -sfrag -srd -var env.nscp_path -out "Components.wxs"
"%WIX_BIN_PATH%candle.exe" ICSW_Windows_Client.wxs
"%WIX_BIN_PATH%candle.exe" Components.wxs
"%WIX_BIN_PATH%candle.exe" HostEditingDlg.wxs
"%WIX_BIN_PATH%light.exe" -ext WixUIExtension ICSW_Windows_Client.wixobj Components.wixobj HostEditingDlg.wixobj -o ICSW_Windows_Client.msi
@pause

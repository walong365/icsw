SET NSCP_VERSION=0.4.4.23
SET WINPYTH_MAJOR=5
SET WINPYTH_MINOR=1
SET WINPYTH_MINORFIX=3
SET WIX_BIN_PATH=C:\Program Files (x86)\WiX Toolset v3.10\bin\


bin\wget https://github.com/mickem/nscp/releases/download/%NSCP_VERSION%/nscp-%NSCP_VERSION%-Win32.zip
bin\7z -o.\nscp x nscp-%NSCP_VERSION%-Win32.zip 

bin\wget https://sourceforge.net/projects/winpython/files/WinPython_3.%WINPYTH_MAJOR%/3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%/WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%.exe
bin\7z -o.\tmp x WinPython-64bit-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.%WINPYTH_MINORFIX%.exe
MOVE .\tmp\$_OUTDIR\python-3.%WINPYTH_MAJOR%.%WINPYTH_MINOR%.amd64 .\nscp\python
COPY .\nscp\python\pywintypes3%WINPYTH_MAJOR%.dll .\nscp\
COPY .\scripts\* .\nscp\scripts\python\
COPY .\scripts\finalize-install.py .\nscp\


SET nscp_path=nscp
"%WIX_BIN_PATH%heat.exe" dir nscp -cg NscpFiles -dr INSTALLDIR -gg -scom -sreg -sfrag -srd -var env.nscp_path -out "Components.wxs"
"%WIX_BIN_PATH%candle.exe" ICSW_Windows_Client.wxs
"%WIX_BIN_PATH%candle.exe" Components.wxs
"%WIX_BIN_PATH%candle.exe" HostEditingDlg.wxs
"%WIX_BIN_PATH%light.exe" -ext WixUIExtension ICSW_Windows_Client.wixobj Components.wixobj HostEditingDlg.wixobj -o ICSW_Windows_Client.msi
@pause

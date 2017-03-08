SET WIX_BIN_PATH=C:\Program Files (x86)\WiX Toolset v3.10\bin\
SET PYTHON27_PATH=C:\Python27\

:: Generate/fetch required executables
..\windows_common_files\bin\wget --no-check-certificate -nc https://the.earth.li/~sgtatham/putty/latest/w32/putty.exe

"%PYTHON27_PATHpython.exe" -m pip install pyinstaller
"%PYTHON27_PATHpython.exe" -m PyInstaller -F -w icsw_remote_viewer_windows.py

MOVE .\dist\icsw_remote_viewer_windows.exe .\

"%WIX_BIN_PATH%candle.exe" ICSW_Remote_Viewer.wxs
"%WIX_BIN_PATH%light.exe" -ext WixUIExtension -dWixUILicenseRtf=..\windows_common_files\legal_text.rtf -dWixUIBannerBmp=..\windows_common_files\WixUIBannerBmp.bmp -dWixUIExclamationIco=..\windows_common_files\WixUIExclamationIco.ico -dWixUIDialogBmp=..\windows_common_files\WixUIDialogBmp.bmp ICSW_Remote_Viewer.wixobj -o ICSW_Remote_Viewer.msi

:: Cleanup temporary files
DEL .\*.wixobj
DEL .\*.wixpdb
RMDIR /s /q .\dist
RMDIR /s /q .\build

@pause

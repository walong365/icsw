SET WIX_BIN_PATH=C:\Program Files (x86)\WiX Toolset v3.10\bin\

"%WIX_BIN_PATH%candle.exe" ICSW_Remote_Viewer.wxs
"%WIX_BIN_PATH%light.exe" -ext WixUIExtension -dWixUILicenseRtf=..\windows_common_files\legal_text.rtf -dWixUIBannerBmp=..\windows_common_files\WixUIBannerBmp.bmp -dWixUIExclamationIco=..\windows_common_files\WixUIExclamationIco.ico -dWixUIDialogBmp=..\windows_common_files\WixUIDialogBmp.bmp ICSW_Remote_Viewer.wixobj -o ICSW_Remote_Viewer.msi

:: Cleanup temporary files
::RMDIR /s /q .\tmp
::RMDIR /s /q .\host_monitor_windows
::DEL .\Components.wixobj
::DEL .\Components.wxs
::DEL .\ICSW_Windows_Client.wixobj
::DEL .\ICSW_Windows_Client-%HM_VERSION%-%HM_PLATFORM%.wixpdb

@pause

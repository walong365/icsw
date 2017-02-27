# -*- mode: python -*-

block_cipher = None


a = Analysis(['initat/host_monitoring/main_binary.py'],
             pathex=['/home/kaufmann/dev/icsw'],
             binaries=[],
             datas=[('initat/host_monitoring', 'initat/host_monitoring'), ('initat/tools/', 'initat/tools/'), ('opt/cluster/etc', 'opt/cluster/etc'), ('initat/logging_server', 'initat/logging_server'), ('initat/tools/', 'initat/tools/'), ('initat/*.py', 'initat/')],
             hiddenimports=['inflection'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='host_monitoring_bin',
          debug=False,
          strip=True,
          upx=False,
          console=True )

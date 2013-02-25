from distutils.core import setup

setup(name="cbc-tools",
      version="0.1",
      description="cbc tools from the INIT(c) cluster software",
      url="http://www.init.at",
      author="Andreas Lang-Nevyjel",
      author_email="lang-nevyjel@init.at",
      py_modules=["compile_tools"],
      scripts=["compile_libgoto.py", "compile_openmpi.py", "compile_hpl.py",
               "compile_fftw.py", "read_bonnie.py", "bonnie.py", "n_from_mem.py",
               "read_hpl_result.py", "check_vasp.py"],
      )

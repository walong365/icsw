PYTHON=python-init

build:
	${PYTHON} setup.py build

install:
	${PYTHON} setup.py install --root="${DESTDIR}"

clean:
	rm -rf build dist

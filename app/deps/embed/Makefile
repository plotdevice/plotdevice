REPO = https://github.com/gregneagle/relocatable-python.git
BUILD_OPTS = --os-version=11 --python-version=3.10.5 --upgrade-pip --pip-requirements=requirements.txt

Python.framework: relocatable-python
	python3 ./relocatable-python/make_relocatable_python_framework.py $(BUILD_OPTS)

relocatable-python:
	git clone $(REPO)

clean:
	rm -r Python.framework
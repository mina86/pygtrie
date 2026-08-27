all: test lint coverage docs build

test: test.py pygtrie.py
	python3 -X dev $<
	python3 -X dev -m doctest pygtrie.py

lint: .pylintrc pygtrie.py test.py example.py
	lint=$$(which pylint3 2>/dev/null) || lint=$$(which pylint) && \
	"$$lint" --rcfile $^

coverage: test.py pygtrie.py
	python3-coverage run --source=pygtrie $< && \
		python3-coverage report -m

build:
	python3 -m build -swn

docs:
	python3 setup.py build_doc

.PHONY: all test lint coverage build docs

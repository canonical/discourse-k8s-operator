blacken:
	@echo "Normalising python layout with black."
	@tox -e black

lint: blacken
	@echo "Running flake8"
	@tox -e lint

# We actually use the build directory created by charmcraft,
# but the .charm file makes a much more convenient sentinel.
unittest: discourse.charm
	@tox -e unit

test: lint unittest

clean:
	@echo "Cleaning files"
	@git clean -fXd

discourse.charm: src/*.py requirements.txt
	charmcraft build

.PHONY: blacken lint test unittest clean

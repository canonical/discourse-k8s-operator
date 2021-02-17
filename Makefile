DISCOURSE_VERSION ?= v2.6.1
IMAGE_VERSION ?= $(DISCOURSE_VERSION)
IMAGE_NAME ?=discourse

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

build-image:
	@echo "Building the image."
	@docker build \
                --no-cache=true \
                --build-arg CONTAINER_APP_VERSION='$(DISCOURSE_VERSION)' \
                -t $(IMAGE_NAME):$(IMAGE_VERSION) \
                image/

build-image-markdown-saml:
	@echo "Building the image."
	@docker build \
                --no-cache=true \
                --build-arg CONTAINER_APP_VERSION='$(DISCOURSE_VERSION)' \
                -t $(IMAGE_NAME)-markdown-saml:$(IMAGE_VERSION) \
		--target markdown-saml \
                image/

.PHONY: blacken lint test unittest clean build-image

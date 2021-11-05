DISCOURSE_VERSION ?= v2.8.0.beta7
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
unittest: discourse-k8s.charm
	@tox -e unit

test: lint unittest

clean:
	@echo "Cleaning files"
	@git clean -fXd

discourse-k8s.charm: src/*.py requirements.txt
	charmcraft build

build-image:
	@echo "Building the default image."
	@docker build \
                --no-cache=true \
                --build-arg CONTAINER_APP_VERSION='$(DISCOURSE_VERSION)' \
                -t $(IMAGE_NAME):$(IMAGE_VERSION) \
                image/

build-image-markdown-saml:
	@echo "Building the markdown-saml image."
	@docker build \
                --no-cache=true \
                --build-arg CONTAINER_APP_VERSION='$(DISCOURSE_VERSION)' \
                -t $(IMAGE_NAME)-markdown-saml:$(IMAGE_VERSION) \
		--target markdown-saml \
                image/

push-image-local-registry:
	@echo "Pushing the default image to local registry"
	@docker tag $(IMAGE_NAME):$(IMAGE_VERSION) localhost:32000/$(IMAGE_NAME):$(IMAGE_VERSION)
	@docker push localhost:32000/$(IMAGE_NAME):$(IMAGE_VERSION)

.PHONY: blacken lint test unittest clean build-image

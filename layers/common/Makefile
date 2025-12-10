# Makefile for building Lambda Layer
# SAM uses this to build the layer correctly

build-CommonLayer:
	mkdir -p "$(ARTIFACTS_DIR)/python"
	cp -r python/common "$(ARTIFACTS_DIR)/python/"
	python3.12 -m pip install -r requirements.txt -t "$(ARTIFACTS_DIR)/python"

.DEFAULT_GOAL := help

# The spacing and comments in this Makefile are intentionally formatted to
# allow the `make` command to display a nicely formatted list of available
# targets and their descriptions.

# Single hash symbols (#) are used for comments that are not displayed in
# the `make` output, while double hash symbols (##) are used for comments
# that are displayed when running `make` without any arguments or with the
# `make help` command.

# To add breaks between sections in the `make` output, simply add a comment line with
# double hash symbols and some spacing, as shown below.

## 
## -----------------------------------------------
## Makefile for GitHub Repositry Archive Script
## -----------------------------------------------
## 

.PHONY: help
help:				## This help message.
	@sed -ne '/@sed/!s/## //p' $(MAKEFILE_LIST)

## 

.PHONY: clean
clean: 			## Clean the temporary files.
	rm -rf megalinter-reports
	rm -rf site
	rm -rf dist
	rm -rf build
	rm -rf tmp
	rm -rf outputs
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	rm -rf .pytest_cache
	rm -rf .coverage
	find . -type d -name '__pycache__' -exec rm -rf {} +
	rm -rf build
	rm -rf tmp

##

# Dependency installation

.PHONY: install
install:  		## Install the dependencies excluding dev.
	poetry install --only main

##

.PHONY: install-dev
install-dev:  		## Install the dependencies including dev.
	poetry install

##

.PHONY: install-docs
install-docs:  		## Install only the documentation dependencies
	poetry install --only docs

##

# Formatting

.PHONY: format
format:  		## Format the code.
	poetry run black src
	poetry run ruff check src --fix

##

# Linting

.PHONY: md-fix
md-fix: 		## Run markdown linting with Markdownlint and fix issues.
	sh ./shell_scripts/md_fix.sh

##

.PHONY: mypy
mypy:  			## Run mypy.
	poetry run mypy src

##

.PHONY: lint
lint:  			## Run all linters (black/ruff/pylint/mypy/markdownlint).
	poetry run black --check src
	poetry run ruff check src
	make md-fix
	make mypy

##

.PHONY: megalint
megalint:  		## Run the mega-linter.
	docker run --platform linux/amd64 --rm \
		-v /var/run/docker.sock:/var/run/docker.sock:rw \
		-v $(shell pwd):/tmp/lint:rw \
		oxsecurity/megalinter:v8

##

# Testing

.PHONY: test
test:  			## Run the tests and check coverage.
	poetry run pytest -n auto --cov=src --cov-report term-missing --cov-fail-under=95

##

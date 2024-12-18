# GitHub Repository Archive Script

A Python utility used to archive old, unused GitHub repositories from an organisation.

## Makefile

This repository makes use of a Makefile to execute common commands. To view all commands, execute `make all`.

```bash
make all
```

## Linting and Testing

### GitHub Actions

This file contains 2 GitHub Actions to automatically lint and test code on pull request creation and pushing to the main branch.

- [`ci.yml`](./.github/workflows/ci.yml)
- [`mega-linter.yml`](./.github/workflows/mega-linter.yml)

### Running Tests Locally

To lint and test locally, you need to:

1. Install dev dependencies

    ```bash
    make install-dev
    ```

2. Run all the linters

    ```bash
    make lint
    ```

3. Run all the tests

    ```bash
    make test
    ```

4. Run Megalinter

    ```bash
    make megalint
    ```

**Please Note:** This requires a docker daemon to be running. We recommend using [Colima](https://github.com/abiosoft/colima) if using MacOS or Linux. A docker daemon is required because Megalinter is ran from a docker image.

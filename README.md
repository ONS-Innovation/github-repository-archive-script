# GitHub Repository Archive Script

A Python utility used to archive old, unused GitHub repositories from an organisation.

## Prerequisites

- A Docker Daemon (Colima is recommended)
  - [Colima](https://github.com/abiosoft/colima)
- Terraform (For deployment)
  - [Terraform](https://www.terraform.io/)
- Python >3.12
  - [Python](https://www.python.org/)
- Make
  - [GNU make](https://www.gnu.org/software/make/manual/make.html#Overview)

## Makefile

This repository makes use of a Makefile to execute common commands. To view all commands, execute `make all`.

```bash
make all
```

## Development

To work on this project, you need to:

1. Create a virtual environment and activate it.

    Create:

    ```python
    python3 -m venv venv
    ```

    Activate:

    ```python
    source venv/bin/activate
    ```

2. Install dependencies

    Production dependencies only:

    ```bash
    make install
    ```

    Dependencies including dev dependencies (used for Linting and Testing)

    ```bash
    make install-dev
    ```

To run the project during development, we recommend you [run the project outside of a container](#outside-of-a-container-development-only)

## Running the Project

### Containerised (Recommended)

To run the project, a Docker Daemon is required to containerise and execute the project. We recommend using [Colima](https://github.com/abiosoft/colima).

Before the doing the following, make sure your Daemon is running. If using Colima, run `colima start` to check this.

1. Containerise the project.

    ```bash
    docker build -t github-repository-archive-script .
    ```

2. Check the image exists (Optional).

    ```bash
    docker images
    ```

    Example Output:

    ```bash
    REPOSITORY                         TAG       IMAGE ID       CREATED          SIZE
    github-repository-archive-script   latest    b4a1e32ce51b   12 minutes ago   840MB
    ```

3. Run the image.

    ```bash
    docker run --platform linux/amd64 -p 9000:8080 \
    -e AWS_ACCESS_KEY_ID=<access_key_id> \
    -e AWS_SECRET_ACCESS_KEY=<secret_access_key> \
    -e AWS_DEFAULT_REGION=<region> \
    -e AWS_SECRET_NAME=<secret_name> \
    -e GITHUB_ORG=<org> \
    -e GITHUB_APP_CLIENT_ID=<client_id> \
    -e AWS_LAMBDA_FUNCTION_TIMEOUT=300
    github-repository-archive-script
    ```

    When running the container, you are required to pass some environment variable.

    | Variable                    | Description                                                                               |
    |-----------------------------|-------------------------------------------------------------------------------------------|
    | GITHUB_ORG                  | The organisation you would like to run the tool in.                                       |
    | GITHUB_APP_CLIENT_ID        | The Client ID for the GitHub App which the tool uses to authenticate with the GitHub API. |
    | AWS_DEFAULT_REGION          | The AWS Region which the Secret Manager Secret is in.                                     |
    | AWS_SECRET_NAME             | The name of the AWS Secret Manager Secret to get.                                         |
    | AWS_LAMBDA_FUNCTION_TIMEOUT | The timeout time in seconds (Default: 300s / 5 minutes).                                  |

    Once the container is running, a local endpoint is created at `localhost:9000/2015-03-31/functions/function/invocations`.

4. Check the container is running (Optional).

    ```bash
    docker ps
    ```

    Example Output:

    ```bash
    CONTAINER ID   IMAGE                              COMMAND                  CREATED         STATUS         PORTS                                       NAMES
    ca890d30e24d   github-repository-archive-script   "/lambda-entrypoint.…"   5 seconds ago   Up 4 seconds   0.0.0.0:9000->8080/tcp, :::9000->8080/tcp   recursing_bartik
    ```

5. Post to the endpoint (`localhost:9000/2015-03-31/functions/function/invocations`).

    ```bash
    curl "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{}'
    ```

    This will run the Lambda function and, once complete, will return a success message.

6. After testing stop the container.

    ```bash
    docker stop <container_id>
    ```

### Outside of a Container (Development only)

To run the Lambda function outside of a container, we need to execute the `handler()` function.

1. Uncomment the following at the bottom of `main.py`.

    ```python
    ...
    # if __name__ == "__main__":
    #     handler(None, None)
    ...
    ```

    **Please Note:** If uncommenting the above in `main.py`, make sure you re-comment the code *before* pushing back to GitHub.

2. Export the required environment variables:

    ```bash
    export AWS_ACCESS_KEY_ID=<access_key_id>
    export AWS_SECRET_ACCESS_KEY=<secret_access_key>
    export AWS_DEFAULT_REGION=eu-west-2
    export AWS_SECRET_NAME=<secret_name>
    export GITHUB_ORG=<org>
    export GITHUB_APP_CLIENT_ID=<client_id>
    ```

    An explanation of each variable is available within the [containerised instructions](#containerised-recommended).

3. Run the script.

    ```bash
    python3 src/main.py
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

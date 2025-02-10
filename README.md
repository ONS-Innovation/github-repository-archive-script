# GitHub Repository Archive Script

A Python utility used to archive old, unused GitHub repositories from an organisation.

## Table of Contents

- [GitHub Repository Archive Script](#github-repository-archive-script)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Makefile](#makefile)
  - [Development](#development)
  - [Running the Project](#running-the-project)
    - [Containerised (Recommended)](#containerised-recommended)
    - [Outside of a Container (Development only)](#outside-of-a-container-development-only)
  - [Deployment](#deployment)
    - [Overview](#overview)
    - [Deployment Prerequisites](#deployment-prerequisites)
    - [Storing the Container on AWS Elastic Container Registry (ECR)](#storing-the-container-on-aws-elastic-container-registry-ecr)
    - [Deploying the Lambda](#deploying-the-lambda)
    - [Destroying / Removing the Lambda](#destroying--removing-the-lambda)
  - [Linting and Testing](#linting-and-testing)
    - [GitHub Actions](#github-actions)
    - [Running Tests Locally](#running-tests-locally)

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

## Deployment

### Overview

This repository is designed to be hosted on AWS Lambda using a container image as the Lambda's definition.

There are 2 parts to deployment:

1. Updating the ECR Image.
2. Updating the Lambda.

### Deployment Prerequisites

Before following the instructions below, we assume that:

- An ECR repository exists on AWS that aligns with the Lambda's naming convention, `{env_name}-{lambda_name}` (these can be set within the `.tfvars` file. See [example_tfvars.txt](./terraform/service/env/dev/example_tfvars.txt)).
- The AWS account contains underlying infrastructure to deploy on top of. This infrastructure is defined within [sdp-infrastructure](https://github.com/ONS-Innovation/sdp-infrastructure) on GitHub.
- An AWS IAM user has been setup with appropriate permissions.

Additionally, we recommend that you keep the container versioning in sync with GitHub releases. Internal documentation for this is available on Confluence ([GitHub Releases and AWS ECR Versions](https://confluence.ons.gov.uk/display/KEH/GitHub+Releases+and+AWS+ECR+Versions)). We follow Semantic Versioning ([Learn More](https://semver.org/spec/v2.0.0.html)).

### Storing the Container on AWS Elastic Container Registry (ECR)

When changes are made to the repository's source code, the code must be containerised and pushed to AWS for the lambda to use.

The following instructions deploy to an ECR repository called `sdp-dev-repository-archive-script`. Please change this to `<env_name>-<lambda_name>` based on your AWS instance.

All of the commands (steps 2-5) are available for your environment within the AWS GUI. Navigate to ECR > {repository_name} > View push commands.

1. Export AWS credential into the environment. This makes it easier to ensure you are using the correct credentials.

    ```bash
    export AWS_ACCESS_KEY_ID="<aws_access_key_id>"
    export AWS_SECRET_ACCESS_KEY="<aws_secret_access_key>"
    ```

2. Login to AWS.

    ```bash
    aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.eu-west-2.amazonaws.com
    ```

3. Ensuring you're at the root of the repository, build a docker image of the project.

    ```bash
    docker build -t sdp-dev-github-repository-archive-script .
    ```

    **Please Note:** Change `sdp-dev-github-repository-archive-script` within the above command to `<env_name>-<lambda_name>`.

4. Tag the docker image to push to AWS, using the correct versioning mentioned in [prerequisites](#deployment-prerequisites).

    ```bash
    docker tag sdp-dev-github-repository-archive-script:latest <aws_account_id>.dkr.ecr.eu-west-2.amazonaws.com/sdp-dev-github-repository-archive-script:<semantic_version>
    ```

    **Please Note:** Change `sdp-dev-github-repository-archive-script` within the above command to `<env_name>-<lambda_name>`.

5. Push the image to ECR.

    ```bash
    docker push <aws_account_id>.dkr.ecr.eu-west-2.amazonaws.com/sdp-dev-github-repository-archive-script:<semantic_version>
    ```

Once pushed, you should be able to see your new image version within the ECR repository.

### Deploying the Lambda

Once AWS ECR has the new container image, we need to update the Lambda's configuration to use it. To do this, use the repository's provided [Terraform](./terraform/).

Within the terraform directory, there is a [service](./terraform/service/) subdirectory which contains the terraform to setup the lambda on AWS.

1. Change directory to the service terraform.

    ```bash
    cd terraform/service
    ```

2. Fill out the appropriate environment variables file
    - `env/dev/dev.tfvars` for sdp-dev.
    - `env/prod/prod.tfvars` for sdp-prod.

    These files can be created based on [`example_tfvars.txt`](./terraform/service/env/dev/example_tfvars.txt).

    **It is crucial that the completed `.tfvars` file does not get committed to GitHub.**

3. Initialise the terraform using the appropriate `.tfbackend` file for the environment (`env/dev/backend-dev.tfbackend` or `env/prod/backend-prod.tfbackend`).

    ```bash
    terraform init -backend-config=env/dev/backend-dev.tfbackend -reconfigure
    ```

    **Please Note:** This step requires an AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to be loaded into the environment if not already in place. This can be done using:

    ```bash
    export AWS_ACCESS_KEY_ID="<aws_access_key_id>"
    export AWS_SECRET_ACCESS_KEY="<aws_secret_access_key>"
    ```

4. Refresh the local state to ensure it is in sync with the backend, using the appropriate `.tfvars` file for the environment (`env/dev/dev.tfvars` or `env/prod/prod.tfvars`).

    ```bash
    terraform refresh -var-file=env/dev/dev.tfvars
    ```

5. Plan the changes, using the appropriate `.tfvars` file.

    i.e. for dev use

    ```bash
    terraform plan -var-file=env/dev/dev.tfvars
    ```

6. Apply the changes, using the appropriate `.tfvars` file.

    i.e. for dev use

    ```bash
    terraform apply -var-file=env/dev/dev.tfvars
    ```

Once applied successfully, the Lambda and EventBridge Schedule will be created.

### Destroying / Removing the Lambda

To delete the service resources, run the following:

```bash
cd terraform/service
terraform init -backend-config=env/dev/backend-dev.tfbackend -reconfigure
terraform refresh -var-file=env/dev/dev.tfvars
terraform destroy -var-file=env/dev/dev.tfvars
```

**Please Note:** Make sure to use the correct `.tfbackend` and `.tfvars` files for your environment.

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

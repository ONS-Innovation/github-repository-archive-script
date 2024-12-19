import datetime
import logging
import os
from pprint import pprint
from typing import Any, Optional

import boto3
import github_api_toolkit


def get_environment_variable(variable_name: str) -> str:
    """Gets an environment variable and raises an exception if it is not found.

    Args:
        variable_name (str): The name of the environment variable to get.

    Raises:
        Exception: If the environment variable is not found.

    Returns:
        str: The value of the environment variable.
    """
    variable = os.getenv(variable_name)
    if variable is None:
        error_message = f"{variable_name} environment variable not found. Please check your environment variables."
        logger.error(error_message)
        raise Exception(error_message)
    return variable


# region Setup Logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

## Get the debug environment variable

debug_value = get_environment_variable("DEBUG")

## Convert the debug environment variable to a boolean

if debug_value.lower() == "true":
    debug = True
elif debug_value.lower() == "false":
    debug = False
else:
    message = "DEBUG environment variable must be 'true' or 'false'."
    logger.error(message)
    raise Exception(message)

if debug:
    logging.basicConfig(filename="debug.log", level=logging.DEBUG)

    # Delete the log file if it exists
    if os.path.exists("debug.log"):
        os.remove("debug.log")


def log_api_request(response_status: int, query: str, variables: dict) -> None:
    """Logs the response of a GraphQL request.

    Args:
        response_status (int): The status code of the response.
        query (str): The query that was sent.
        variables (dict): The variables that were sent with the query.
    """
    logger.info("GraphQL Request", extra={"query": query, "variables": variables, "response_status": response_status})


# endregion

# region Import Environment Variables

## GitHub Variables

org = get_environment_variable("GITHUB_ORG")
app_client_id = get_environment_variable("GITHUB_APP_CLIENT_ID")

## AWS Variables

aws_default_region = get_environment_variable("AWS_DEFAULT_REGION")
aws_secret_name = get_environment_variable("AWS_SECRET_NAME")

aws_account = get_environment_variable("AWS_ACCOUNT_NAME")
aws_bucket = f"{aws_account}-repository-archive-script"

# endregion

# region Create AWS Boto3 Instances

session = boto3.Session()

## Secret Manager

secret_manager = session.client(service_name="secretsmanager", region_name=aws_default_region)

## S3

s3 = session.client(service_name="s3", region_name=aws_default_region)

# endregion

# region Create GitHub GraphQL Controller

## Get GitHub App .pem file from AWS

response = secret_manager.get_secret_value(SecretId=aws_secret_name)

pem_contents = response.get("SecretString", "")

if pem_contents == "":
    message = ".pem file not found in AWS Secrets Manager. Please check your environment variables."
    logger.error(message)
    raise Exception(message)

## Exchange the .pem file for an access token

token = github_api_toolkit.get_token_as_installation(org=org, pem_contents=pem_contents, app_client_id=app_client_id)

if type(token) is not tuple:
    logger.error(token)
    raise Exception(token)

token = token[0]

## Create an instance of the GraphQL interface

ql = github_api_toolkit.github_graphql_interface(token=token)

## Test the GraphQL interface

query = """
    query {
        viewer {
            login
        }
    }
"""

response = ql.make_ql_request(query, {})

log_api_request(response.status_code, query, {})

response.raise_for_status()

logger.info("Test GraphQL Request OK")

# endregion

# region Get Repositories


def get_repository_page(org: str, max_repos: int, cursor: Optional[str] = None) -> Any:
    """Gets a page of non-archived repositories from a GitHub organization.

    Args:
        org (str): The name of the GitHub organization.
        max_repos (int): The maximum number of repositories to get.
        cursor (str, optional): The cursor to get the next page of repositories. Defaults to None.

    Returns:
        dict: The response from the GraphQL request.
    """
    logger.info(f"Getting repositories for {org} with a maximum of {max_repos} repositories. Cursor: {cursor}")

    query = """
        query($org: String!, $max_repos: Int, $cursor: String) {
            organization(login: $org) {
                repositories(first: $max_repos, isArchived: false, after: $cursor) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        name
                        updatedAt
                        issues(first: 1, filterBy: {labels: ["archive"]}) {
                            nodes {
                                title
                                createdAt
                            }
                        }
                    }
                }
            }
        }
    """

    variables = {"org": org, "max_repos": max_repos, "cursor": cursor}

    response = ql.make_ql_request(query, variables)

    log_api_request(response.status_code, query, variables)

    response.raise_for_status()

    return response.json()


repositories = []
number_of_pages = 1

response_json = get_repository_page(org, 100)

repositories.extend(response_json["data"]["organization"]["repositories"]["nodes"])

while response_json["data"]["organization"]["repositories"]["pageInfo"]["hasNextPage"]:
    cursor = response_json["data"]["organization"]["repositories"]["pageInfo"]["endCursor"]

    print(f"Getting page {number_of_pages + 1} with cursor {cursor}.")
    logger.info(f"Getting page {number_of_pages + 1} with cursor {cursor}.")

    response_json = get_repository_page(org, 100, cursor)
    repositories.extend(response_json["data"]["organization"]["repositories"]["nodes"])

    number_of_pages += 1

print(f"Found {len(repositories)} repositories in {number_of_pages} page(s).")
logger.info(f"Found {len(repositories)} repositories in {number_of_pages} page(s).")

# endregion

# region Archive Process

for repository in repositories:

    pprint(repository)

    repository_last_updated = datetime.datetime.strptime(repository["updatedAt"], "%Y-%m-%dT%H:%M:%SZ")
    one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)

    # If the repository has been updated in the last year, skip it
    if repository_last_updated > one_year_ago:
        continue

    # If the repository has an issue with the label 'archive',
    # Check if the repository is exempt from archiving
    # Check if the repository issue has been open for more than 30 days
    # If not exempt and the issue has been open for more than 30 days, archive the repository
    if repository["issues"]["nodes"]:
        print("TODO: Check for exemption and issue age")

        print(repository["issues"]["nodes"][0]["title"])
        print(repository["issues"]["nodes"][0]["createdAt"])

        print("TODO: Archive repository")
    else:
        # If the repository does not have an issue with the label 'archive',
        # Create an issue with the label 'archive' and a message to the repository owner/contributors
        print("TODO: Make issue")

# endregion

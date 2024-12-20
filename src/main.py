import datetime
import json
import logging
import os
import time
from functools import wraps
from typing import Any, Callable, Optional, ParamSpec, TypeVar

import boto3
import github_api_toolkit

T = TypeVar("T")
P = ParamSpec("P")


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


def get_dict_value(dictionary: dict, key: str) -> Any:
    """Gets a value from a dictionary and raises an exception if it is not found.

    Args:
        dictionary (dict): The dictionary to get the value from.
        key (str): The key to get the value for.

    Raises:
        Exception: If the key is not found in the dictionary.

    Returns:
        Any: The value of the key in the dictionary.
    """
    value = dictionary.get(key)

    if value is None:
        raise Exception(f"Key {key} not found in the dictionary.")

    return value


def retry_on_error(max_retries: int = 3, delay: int = 2) -> Any:
    """A decorator that retries a function if an exception is raised.

    Args:
        max_retries (int, optional): The number of times the function should be retried before failing. Defaults to 3.
        delay (int, optional): The time delay in seconds between retry attempts. Defaults to 2.

    Raises:
        Exception: If the function fails after the maximum number of retries.

    Returns:
        Any: The result of the function.
    """

    def decorator(func: Callable[P, T]) -> Any:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any | None:
            retries = 0
            while retries < max_retries:
                try:
                    result = func(*args, **kwargs)
                    if result is not None:  # Check if request was successful
                        return result
                    raise Exception("Request failed with None result")
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"Failed after {max_retries} retries: {e!s}")
                        raise Exception from e
                    logger.warning(f"Attempt {retries} failed. Retrying in {delay} seconds...")
                    time.sleep(delay)
            return None

        return wrapper

    return decorator


# region Load Configuration File

## Load the configuration file as a dictionary

config_file = "./config/config.json"

if not os.path.exists(config_file):
    message = "Configuration file not found. Please check the path."
    raise Exception(message)

with open(config_file) as f:
    config = json.load(f)

## Get the feature dictionary and archive rules from the config file

features = get_dict_value(config, "features")
archive_rules = get_dict_value(config, "archive_configuration")

# endregion

# region Setup Logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

## Get the debug config value

debug = get_dict_value(features, "show_log_locally")

## Delete the log file if it exists
if os.path.exists("debug.log"):
    os.remove("debug.log")

## If debug is True, log to a file

if debug:
    logging.basicConfig(filename="debug.log", level=logging.DEBUG)


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


@retry_on_error()
def get_repository_page(
    org: str, notification_issue_tag: str, exemption_filename: str, max_repos: int, cursor: Optional[str] = None
) -> Any:
    """Gets a page of non-archived repositories from a GitHub organization.

    Args:
        org (str): The name of the GitHub organization.
        notification_issue_tag (str): The tag of the issue that notifies the repository owner of archiving.
        exemption_filename (str): The name of the file that shows if the repository is exempt from archiving or not.
        max_repos (int): The maximum number of repositories to get.
        cursor (str, optional): The cursor to get the next page of repositories. Defaults to None.

    Returns:
        dict: The response from the GraphQL request.
    """
    logger.info(f"Getting repositories for {org} with a maximum of {max_repos} repositories. Cursor: {cursor}")

    query = """
        query($org: String!, $notification_issue_tag: String!, $exemption_filename_main: String!, $exemption_filename_master: String!, $max_repos: Int, $cursor: String) {
            organization(login: $org) {
                repositories(first: $max_repos, isArchived: false, after: $cursor) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        name
                        updatedAt
                        issues(first: 1, filterBy: {labels: [$notification_issue_tag]}) {
                            nodes {
                                title
                                createdAt
                            }
                        }
                        archive_exception_main: object(expression: $exemption_filename_main) {
                            ... on Blob {
                                text
                            }
                        }
                        archive_exception_master: object(expression: $exemption_filename_master) {
                            ... on Blob {
                                text
                            }
                        }
                    }
                }
            }
        }
    """

    variables = {
        "org": org,
        "notification_issue_tag": notification_issue_tag,
        "exemption_filename_main": f"main:{exemption_filename}",
        "exemption_filename_master": f"master:{exemption_filename}",
        "max_repos": max_repos,
        "cursor": cursor,
    }

    response = ql.make_ql_request(query, variables)

    log_api_request(response.status_code, query, variables)

    response.raise_for_status()

    return response.json()


repositories = []
number_of_pages = 1

notification_issue_tag = get_dict_value(archive_rules, "notification_issue_tag")
exemption_filename = get_dict_value(archive_rules, "exemption_filename")

response_json = get_repository_page(org, notification_issue_tag, exemption_filename, 100)

response_repositories = response_json["data"]["organization"]["repositories"]["nodes"]

## Remove None values from the response

response_repositories = [repository for repository in response_repositories if repository is not None]

## Log any error repositories

error_repositories = response_json.get("errors", None)

if error_repositories is not None:
    logger.error(f"Error repositories: {error_repositories}")

repositories.extend(response_repositories)

while response_json["data"]["organization"]["repositories"]["pageInfo"]["hasNextPage"]:
    cursor = response_json["data"]["organization"]["repositories"]["pageInfo"]["endCursor"]

    print(f"Getting page {number_of_pages + 1} with cursor {cursor}.")
    logger.info(f"Getting page {number_of_pages + 1} with cursor {cursor}.")

    response_json = get_repository_page(org, notification_issue_tag, exemption_filename, 100, cursor)

    response_repositories = response_json["data"]["organization"]["repositories"]["nodes"]

    ## Remove None values from the response

    response_repositories = [repository for repository in response_repositories if repository is not None]

    ## Log any error repositories

    error_repositories = response_json.get("errors", None)

    if error_repositories is not None:
        logger.error(f"Error repositories: {error_repositories}")

    repositories.extend(response_repositories)

    number_of_pages += 1

print(f"Found {len(repositories)} repositories in {number_of_pages} page(s).")
logger.info(f"Found {len(repositories)} repositories in {number_of_pages} page(s).")

# endregion

# region Archive Process

## Load the archive rules from the configuration file

archive_threshold = get_dict_value(archive_rules, "archive_threshold")
notification_period = get_dict_value(archive_rules, "notification_period")

## Iterate through the repositories and apply the archive rules

for repository in repositories:

    try:
        repository_last_updated = datetime.datetime.strptime(repository["updatedAt"], "%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        logger.error(f"Error parsing repository last updated date: {e!s}")
        continue

    one_year_ago = datetime.datetime.now() - datetime.timedelta(days=archive_threshold)

    # If the repository has been updated in the last year, skip it
    if repository_last_updated > one_year_ago:
        continue

    print(f"Repository: {repository['name']}")

    # If the repository has an issue with the label 'archive',
    # Check if the repository is exempt from archiving
    # Check if the repository issue has been open for more than 30 days
    # If not exempt and the issue has been open for more than 30 days, archive the repository
    if len(repository["issues"]["nodes"]):
        print("TODO: Check for exemption and issue age")

        print("TODO: Archive repository")
    else:
        # If the repository does not have an issue with the label 'archive',
        # Create an issue with the label 'archive' and a message to the repository owner/contributors
        print("TODO: Make issue")

# endregion

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


def log_api_request(api_type: str, response_status: int, query: str, variables: dict) -> None:
    """Logs the response of a GraphQL request.

    Args:
        api_type (str): The type of API that was used (GraphQL or REST).
        response_status (int): The status code of the response.
        query (str): The query that was sent or the endpoint that was hit.
        variables (dict): The variables that were sent with the query.
    """
    logger.info(
        f"{api_type} Request", extra={"query": query, "variables": variables, "response_status": response_status}
    )


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

# region Create GitHub API Controllers

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

log_api_request("GraphQL", response.status_code, query, {})

response.raise_for_status()

logger.info("Test GraphQL Request OK")

## Create an instance of the REST interface

rest = github_api_toolkit.github_interface(token=token)

## Test the REST interface

endpoint = f"/orgs/{org}/repos"

response = rest.get(endpoint)

log_api_request("REST", response.status_code, endpoint, {})

response.raise_for_status()

logger.info("Test REST Request OK")

# endregion

# region Get Repositories


@retry_on_error()
def get_repository_page(org: str, notification_issue_tag: str, max_repos: int, cursor: Optional[str] = None) -> Any:
    """Gets a page of non-archived repositories from a GitHub organization.

    Args:
        org (str): The name of the GitHub organization.
        notification_issue_tag (str): The tag of the issue that notifies the repository owner of archiving.
        max_repos (int): The maximum number of repositories to get.
        cursor (str, optional): The cursor to get the next page of repositories. Defaults to None.

    Returns:
        dict: The response from the GraphQL request.
    """
    logger.info(f"Getting repositories for {org} with a maximum of {max_repos} repositories. Cursor: {cursor}")

    query = """
        query($org: String!, $notification_issue_tag: String!, $max_repos: Int, $cursor: String) {
            organization(login: $org) {
                repositories(first: $max_repos, isArchived: false, after: $cursor) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        name
                        updatedAt
                        issues(first: 1, filterBy: {labels: [$notification_issue_tag], states: OPEN}) {
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

    variables = {
        "org": org,
        "notification_issue_tag": notification_issue_tag,
        "max_repos": max_repos,
        "cursor": cursor,
    }

    response = ql.make_ql_request(query, variables)

    log_api_request("GraphQL", response.status_code, query, variables)

    response.raise_for_status()

    return response.json()


repositories = []
number_of_pages = 1

notification_issue_tag = get_dict_value(archive_rules, "notification_issue_tag")
exemption_filename = get_dict_value(archive_rules, "exemption_filename")

response_json = get_repository_page(org, notification_issue_tag, 100)

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
maximum_notifications = get_dict_value(archive_rules, "maximum_notifications")

notification_issue_title = "Repository Archive Notice"
notification_issue_body_tuple = (
    "## Important Notice \n\n",
    f"This repository has not been updated in over {archive_threshold} days and will be archived in {notification_period} days if no action is taken. \n",
    "## Actions Required to Prevent Archive \n\n",
    f"1. Update the repository by creating/updating a file called `{exemption_filename}`. \n",
    "   - This file should contain the reason why the repository should not be archived. \n",
    "   - If the file already exists, please update it with the latest information. \n",
    "2. Close this issue. \n\n",
    f"After these actions, the repository will be exempt from archive for another {archive_threshold} days. \n\n",
    "If you have any questions, please contact an organization administrator.",
)

notification_issue_body = "".join(notification_issue_body_tuple)

## Iterate through the repositories and apply the archive rules

issues_created = 0

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

    # If the repository has an issue with the label defined in the configuration file,
    # Check if the repository issue has been open for more than 30 days
    # If the issue has been open for more than 30 days, archive the repository
    if len(repository["issues"]["nodes"]):

        issue_created_at = datetime.datetime.strptime(
            repository["issues"]["nodes"][0]["createdAt"], "%Y-%m-%dT%H:%M:%SZ"
        )
        issue_age = datetime.datetime.now() - issue_created_at

        if issue_age.days > notification_period:
            print("TODO: Archive repository")

    # If the repository does not have an issue with the label defined in the configuration file,
    # Create an issue with the label and a message to the repository owner/contributors

    elif issues_created < maximum_notifications:

        endpoint = f"/repos/{org}/{repository['name']}/issues"

        params = {
            "title": notification_issue_title,
            "body": notification_issue_body,
            "labels": [notification_issue_tag],
        }

        response = rest.post(endpoint, params)

        log_api_request("REST", response.status_code, endpoint, params)

        response.raise_for_status()

        logger.info(f"Created issue for repository {repository['name']}")

        issues_created += 1

    elif issues_created == maximum_notifications:
        logger.info("Maximum number of notifications reached. No more notifications will be made.")
        issues_created += 1

# endregion

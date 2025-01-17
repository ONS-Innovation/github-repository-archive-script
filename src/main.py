"""A script to iterate over GitHub repositories and archive them if they're inactive."""

import datetime
import json
import os
import time
from functools import wraps
from typing import Any, Callable, ParamSpec, Tuple, TypeVar, Union

import boto3
import github_api_toolkit

from src.logger import wrapped_logging

T = TypeVar("T")
P = ParamSpec("P")


def get_config_file(path: str) -> Any:
    """Loads a configuration file as a dictionary.

    Args:
        path (str): The path to the configuration file.

    Raises:
        Exception: If the configuration file is not found.

    Returns:
        Any: The configuration file as a dictionary.
    """
    try:
        with open(path) as f:
            config = json.load(f)
    except FileNotFoundError:
        error_message = f"{path} configuration file not found. Please check the path."
        raise Exception(error_message) from None

    if type(config) is not dict:
        error_message = f"{path} configuration file is not a dictionary. Please check the file contents."
        raise Exception(error_message)

    return config


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
        raise Exception(error_message)

    return variable


def get_access_token(secret_manager: Any, secret_name: str, org: str, app_client_id: str) -> Tuple[str, str]:
    """Gets the access token from the AWS Secret Manager.

    Args:
        secret_manager (Any): The Boto3 Secret Manager client.
        secret_name (str): The name of the secret to get.
        org (str): The name of the GitHub organization.
        app_client_id (str): The client ID of the GitHub App.

    Raises:
        Exception: If the secret is not found in the Secret Manager.

    Returns:
        str: The access token.
    """
    response = secret_manager.get_secret_value(SecretId=secret_name)

    pem_contents = response.get("SecretString", "")

    if not pem_contents:
        error_message = (
            f"Secret {secret_name} not found in AWS Secret Manager. Please check your environment variables."
        )
        raise Exception(error_message)

    token = github_api_toolkit.get_token_as_installation(org, pem_contents, app_client_id)

    if type(token) is not tuple:
        raise Exception(token)

    return token


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

            logger = wrapped_logging(False)

            while retries < max_retries:
                try:
                    result = func(*args, **kwargs)
                    if result is not None:  # Check if request was successful
                        return result
                    raise Exception("Request failed with None result")
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        raise Exception(e) from e
                    logger.log_warning(f"Attempt {retries} failed. Retrying in {delay} seconds...")
                    time.sleep(delay)
            return None

        return wrapper

    return decorator


@retry_on_error()
def get_repository_page(
    logger: wrapped_logging,
    ql: github_api_toolkit.github_graphql_interface,
    variables: dict[str, Union[str, int, None]],
) -> Any:
    """Gets a page of non-archived repositories from a GitHub organization.

    Args:
        logger: The logger object.
        ql (github_api_toolkit.github_graphql_interface): The GraphQL interface for the GitHub API.
        variables (dict): The variables to pass to the GraphQL request. This should include the organization name, the notification issue tag, the maximum number of repositories to get, and the cursor.

    Returns:
        dict: The response from the GraphQL request.
    """
    if variables.get("cursor") == "None":
        variables["cursor"] = None

    logger.log_info(
        f"Getting repositories for {get_dict_value(variables, "org")} with a maximum of {get_dict_value(variables, "max_repos")} repositories. Cursor: {variables.get("cursor", "None")}"
    )

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

    response = ql.make_ql_request(query, variables)

    response.raise_for_status()

    logger.log_info(f"Request successsful. Response Status Code: {response.status_code}")

    return response.json()


def clean_repositories(repositories: list[dict]) -> list[dict]:
    """Removes any None values from a list of repositories.

    Args:
        repositories (list[dict]): A list of repositories.

    Returns:
        list[dict]: The list of repositories with None values removed.
    """
    return [repository for repository in repositories if repository is not None]


def log_error_repositories(logger: wrapped_logging, response_json: dict) -> None:
    """Logs any errors in the response from the GitHub API.

    Args:
        logger (wrapped_logging): The logger object.
        response_json (dict): The response from the GitHub API.
    """
    error_repositories = response_json.get("errors")

    if error_repositories is not None:
        logger.log_error(f"Error repositories: {error_repositories}")


def filter_response(logger: wrapped_logging, response_json: dict) -> Any:
    """Filters the response from the GitHub API to get the repositories.

    Args:
        logger (wrapped_logging): The logger object.
        response_json (dict): The response from the GitHub API.

    Returns:
        list[dict]: The list of repositories.
    """
    response_repositories = response_json["data"]["organization"]["repositories"]["nodes"]

    response_repositories = clean_repositories(response_repositories)

    log_error_repositories(logger, response_json)

    return response_repositories


def get_environment_variables() -> Tuple[str, str, str, str]:
    """Gets the environment variables required for the script.

    Raises:
        Exception: If any of the environment variables are not found.

    Returns:
        Tuple[str, str, str, str]: The GitHub organization, the GitHub App client ID, the AWS default region, and the AWS Secret Manager secret name.
    """
    try:
        org = get_environment_variable("GITHUB_ORG")
        app_client_id = get_environment_variable("GITHUB_APP_CLIENT_ID")

        aws_default_region = get_environment_variable("AWS_DEFAULT_REGION")
        aws_secret_name = get_environment_variable("AWS_SECRET_NAME")
    except Exception as e:
        raise Exception(e) from e

    return org, app_client_id, aws_default_region, aws_secret_name


def get_repositories(
    logger: wrapped_logging, ql: github_api_toolkit.github_graphql_interface, org: str, archive_rules: dict
) -> tuple[list[dict], int]:
    """Gets all the repositories from a GitHub organization.

    Args:
        logger (wrapped_logging): The logger object.
        ql (github_api_toolkit.github_graphql_interface): The GraphQL interface for the GitHub API.
        org (str): The name of the GitHub organization.
        archive_rules (dict): The archive rules from the configuration file.

    Returns:
        tuple[list[dict], int]: A tuple containing the list of repositories and the number of pages of repositories.
    """
    repositories = []
    number_of_pages = 1

    notification_issue_tag = get_dict_value(archive_rules, "notification_issue_tag")

    variables = {
        "org": org,
        "notification_issue_tag": notification_issue_tag,
        "max_repos": 100,
        "cursor": "None",
    }

    response_json = get_repository_page(logger, ql, variables)

    response_repositories = filter_response(logger, response_json)

    repositories.extend(response_repositories)

    while response_json["data"]["organization"]["repositories"]["pageInfo"]["hasNextPage"]:
        cursor = response_json["data"]["organization"]["repositories"]["pageInfo"]["endCursor"]

        variables["cursor"] = cursor

        logger.log_info(f"Getting page {number_of_pages + 1} with cursor {cursor}.")

        response_json = get_repository_page(logger, ql, variables)

        response_repositories = filter_response(logger, response_json)

        repositories.extend(response_repositories)

        number_of_pages += 1

    return repositories, number_of_pages


def load_archive_rules(archive_rules: dict) -> Tuple[int, int, str, str, int]:
    """Loads the archive rules from the configuration file.

    Args:
        archive_rules (dict): The archive rules from the configuration file.

    Returns:
        Tuple[int, int, str, str, int]: The archive threshold, the notification period, the notification issue tag, the exemption filename, and the maximum number of notifications.
    """
    archive_threshold = int(get_dict_value(archive_rules, "archive_threshold"))
    notification_period = int(get_dict_value(archive_rules, "notification_period"))
    notification_issue_tag = str(get_dict_value(archive_rules, "notification_issue_tag"))
    exemption_filename = str(get_dict_value(archive_rules, "exemption_filename"))
    maximum_notifications = int(get_dict_value(archive_rules, "maximum_notifications"))

    return archive_threshold, notification_period, notification_issue_tag, exemption_filename, maximum_notifications


def process_repositories(
    interfaces: list[Any],
    org: str,
    repositories: list[dict],
    archive_criteria: list[str],
    notification_content: list[str],
) -> Tuple[int, int]:

    issues_created = 0
    repositories_archived = 0

    logger, rest = interfaces
    archive_threshold, notification_period, notification_issue_tag, maximum_notifications = archive_criteria
    notification_issue_title, notification_issue_body = notification_content

    notice_issued = False

    for repository in repositories:

        last_update_string = get_dict_value(repository, "updatedAt")
        last_update = datetime.datetime.strptime(last_update_string, "%Y-%m-%dT%H:%M:%SZ")

        cut_off_date = datetime.datetime.now() - datetime.timedelta(days=float(archive_threshold))

        # If the repository has been updated in the last year, skip it
        if last_update > cut_off_date:
            continue

        logger.log_info(
            f"Repository {repository['name']} has not been updated in over {archive_threshold} days. Eligible for archiving."
        )

        # If the repository has an issue with the label defined in the configuration file,
        # Check if the repository issue has been open for more than 30 days
        # If the issue has been open for more than 30 days, archive the repository
        if len(repository["issues"]["nodes"]):

            issue_created_at = datetime.datetime.strptime(
                repository["issues"]["nodes"][0]["createdAt"], "%Y-%m-%dT%H:%M:%SZ"
            )
            issue_age = datetime.datetime.now() - issue_created_at

            if issue_age.days > int(notification_period):
                endpoint = f"/repos/{org}/{repository['name']}"

                archive_params = {"archived": True}

                logger.log_info(
                    f"Archiving repository {repository['name']}. Reason: Issue open for {issue_age.days} days."
                )

                response = rest.patch(endpoint, archive_params)

                response.raise_for_status()

                logger.log_info(f"Successfully archived repository {repository['name']}")

                repositories_archived += 1

                continue

            else:
                logger.log_info(
                    f"Issue for repository {repository['name']} open for {issue_age.days} days. This does not meet the notification period ({notification_period} days). Skipping archiving."
                )
                continue

        # If the repository does not have an issue with the label defined in the configuration file,
        # Create an issue with the label and a message to the repository owner/contributors

        if issues_created < int(maximum_notifications):

            # Create Issue Label for Archive Notice if it does not exist

            label_endpoint = f"/repos/{org}/{repository['name']}/labels/{notification_issue_tag}"

            response = rest.get(label_endpoint)

            if "404" in str(response):
                label_params = {
                    "name": notification_issue_tag,
                    "color": "f29513",
                    "description": "This label is used to notify repository owners and contributors of an impending archive.",
                }

                response = rest.post(f"/repos/{org}/{repository['name']}/labels", label_params)

                response.raise_for_status()

                logger.log_info(f"Created label {notification_issue_tag} for repository {repository['name']}.")

            # Create Issue for Archive Notice

            endpoint = f"/repos/{org}/{repository['name']}/issues"

            issue_params = {
                "title": notification_issue_title,
                "body": notification_issue_body,
                "labels": [notification_issue_tag],
            }

            logger.log_info(
                f"Creating issue for repository {repository['name']}. Reason: No issue found with label {notification_issue_tag}."
            )

            response = rest.post(endpoint, issue_params)

            response.raise_for_status()

            logger.log_info(f"Created issue for repository {repository['name']}.")

            issues_created += 1

        elif issues_created == int(maximum_notifications) and not notice_issued:
            logger.log_info("Maximum number of notifications reached. No more notifications will be made.")
            notice_issued = True

        else:
            logger.log_info("Skipping repository. Maximum number of notifications reached.")

    return repositories_archived, issues_created


def handler(event, context) -> str:  # type: ignore[no-untyped-def]

    # Load the configuration file
    config_file_path = "./config/config.json"

    config = get_config_file(config_file_path)

    features = get_dict_value(config, "features")
    archive_rules = get_dict_value(config, "archive_configuration")

    # Initialise logging

    debug = get_dict_value(features, "show_log_locally")

    logger = wrapped_logging(debug)

    logger.log_info("Initialised logging.")

    # Get the environment variables

    org, app_client_id, aws_default_region, aws_secret_name = get_environment_variables()

    logger.log_info("Environment variables retrieved.")

    # Create Boto3 Secret Manager client

    session = boto3.session.Session()
    secret_manager = session.client(service_name="secretsmanager", region_name=aws_default_region)

    logger.log_info("Boto3 Secret Manager client created.")

    # Create GitHub API interfaces (GraphQL and REST)

    token = get_access_token(secret_manager, aws_secret_name, org, app_client_id)

    logger.log_info("Access token for GitHub API retrieved.")

    ql = github_api_toolkit.github_graphql_interface(token[0])
    rest = github_api_toolkit.github_interface(token[0])

    logger.log_info("GitHub API interfaces created.")

    # Get the repositories from GitHub

    repositories, number_of_pages = get_repositories(logger, ql, org, archive_rules)

    logger.log_info(f"Found {len(repositories)} repositories in {number_of_pages} page(s).")

    # Load the archive rules from the configuration file

    archive_threshold, notification_period, notification_issue_tag, exemption_filename, maximum_notifications = (
        load_archive_rules(archive_rules)
    )

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

    # Iterate over the repositories, creating issues and archiving where necessary

    interfaces = [logger, rest]
    archive_criteria = [
        str(archive_threshold),
        str(notification_period),
        str(notification_issue_tag),
        str(maximum_notifications),
    ]
    notification_content = [notification_issue_title, notification_issue_body]

    repositories_archived, issues_created = process_repositories(
        interfaces, org, repositories, archive_criteria, notification_content
    )

    message = f"Script completed. {len(repositories)} repositories checked. {issues_created} issues created. {repositories_archived} repositories archived."

    logger.log_info(message)

    return message

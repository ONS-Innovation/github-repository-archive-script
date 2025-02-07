import datetime
import json
import os
from unittest.mock import MagicMock, call, mock_open, patch

import pytest
from requests import HTTPError, Response

from src.main import (
    clean_repositories,
    filter_response,
    get_access_token,
    get_config_file,
    get_dict_value,
    get_environment_variable,
    get_environment_variables,
    get_repositories,
    get_repository_page,
    handle_response,
    handler,
    load_archive_rules,
    log_error_repositories,
    process_repositories,
    retry_on_error,
)


class TestGetConfigFile:
    def test_get_config_file_success(self):
        mock_data = {"key": "value"}
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
            result = get_config_file("dummy_path")
            assert result == mock_data

    def test_get_config_file_not_found(self):
        with pytest.raises(Exception) as excinfo:
            get_config_file("non_existent_path")
        assert "non_existent_path configuration file not found. Please check the path." in str(excinfo.value)

    def test_get_config_file_not_dict(self):
        mock_data = ["not", "a", "dict"]
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
            with pytest.raises(Exception) as excinfo:
                get_config_file("dummy_path")
            assert "dummy_path configuration file is not a dictionary. Please check the file contents." in str(
                excinfo.value
            )


class TestGetDictValue:
    def test_get_dict_value_success(self):
        dictionary = {"key": "value"}
        result = get_dict_value(dictionary, "key")
        assert result == "value"

    def test_get_dict_value_key_not_found(self):
        dictionary = {"key": "value"}
        with pytest.raises(Exception) as excinfo:
            get_dict_value(dictionary, "non_existent_key")
        assert "Key non_existent_key not found in the dictionary." in str(excinfo.value)


class TestGetEnvironmentVariable:
    def test_get_environment_variable_success(self):
        with patch.dict(os.environ, {"TEST_ENV_VAR": "test_value"}):
            result = get_environment_variable("TEST_ENV_VAR")
            assert result == "test_value"

    def test_get_environment_variable_not_found(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as excinfo:
                get_environment_variable("NON_EXISTENT_ENV_VAR")
            assert (
                "NON_EXISTENT_ENV_VAR environment variable not found. Please check your environment variables."
                in str(excinfo.value)
            )


class TestGetAccessToken:
    def test_get_access_token_success(self):
        secret_manager_mock = patch("boto3.client").start()
        secret_manager_mock.get_secret_value.return_value = {"SecretString": "mock_pem_contents"}
        with patch("github_api_toolkit.get_token_as_installation", return_value=("mock_token", "mock_other_value")):
            result = get_access_token(secret_manager_mock, "mock_secret_name", "mock_org", "mock_app_client_id")
            assert result == ("mock_token", "mock_other_value")

    def test_get_access_token_secret_not_found(self):
        secret_manager_mock = patch("boto3.client").start()
        secret_manager_mock.get_secret_value.return_value = {"SecretString": ""}
        with pytest.raises(Exception) as excinfo:
            get_access_token(secret_manager_mock, "mock_secret_name", "mock_org", "mock_app_client_id")
        assert (
            "Secret mock_secret_name not found in AWS Secret Manager. Please check your environment variables."
            in str(excinfo.value)
        )

    def test_get_access_token_invalid_token(self):
        secret_manager_mock = patch("boto3.client").start()
        secret_manager_mock.get_secret_value.return_value = {"SecretString": "mock_pem_contents"}
        with patch("github_api_toolkit.get_token_as_installation", return_value="error_message"):
            with pytest.raises(Exception) as excinfo:
                get_access_token(secret_manager_mock, "mock_secret_name", "mock_org", "mock_app_client_id")
            assert "error_message" in str(excinfo.value)


class TestRetryOnError:
    def test_retry_on_error_success(self):
        @retry_on_error(max_retries=3, delay=1)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_retry_on_error_failure(self):
        @retry_on_error(max_retries=3, delay=1)
        def failing_function():
            raise Exception("failure")

        with pytest.raises(Exception) as excinfo:
            failing_function()
        assert "failure" in str(excinfo.value)

    def test_retry_on_error_failure_none_result(self):
        @retry_on_error(max_retries=3, delay=1)
        def none_returning_function():
            return None

        with pytest.raises(Exception) as excinfo:
            none_returning_function()
        assert "Request failed with None result" in str(excinfo.value)

    def test_retry_on_error_retries(self):
        max_retries = 3

        @retry_on_error(max_retries=max_retries, delay=1)
        def sometimes_failing_function():
            if sometimes_failing_function.counter < max_retries - 1:
                sometimes_failing_function.counter += 1
                raise Exception("temporary failure")
            return "success"

        sometimes_failing_function.counter = 0

        result = sometimes_failing_function()
        assert result == "success"

    @patch("time.sleep", return_value=None)
    @patch("logging.getLogger")
    def test_retry_on_error_logging(self, mock_get_logger, mock_sleep):
        logger = mock_get_logger.return_value

        max_retries = 3

        @retry_on_error(max_retries=max_retries, delay=1)
        def failing_function():
            raise Exception("temporary failure")

        with pytest.raises(Exception):  # noqa: B017
            failing_function()

        assert logger.warning.call_count == max_retries - 1
        logger.warning.assert_has_calls(
            [call("Attempt 1 failed. Retrying in 1 seconds..."), call("Attempt 2 failed. Retrying in 1 seconds...")]
        )

    def test_retry_on_error_max_returns(self):
        @retry_on_error(max_retries=-1, delay=1)
        def random_function():
            print("This function will never run as max_retries is less than 0")

        assert random_function() is None


class TestGetRepositoryPage:
    @patch("github_api_toolkit.github_graphql_interface")
    @patch("logging.Logger")
    def test_get_repository_page_success(self, mock_logger, mock_ql):
        mock_response = {
            "data": {
                "organization": {
                    "repositories": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "end_cursor"},
                        "nodes": [
                            {
                                "name": "repo1",
                                "updatedAt": "2023-01-01T00:00:00Z",
                                "issues": {"nodes": [{"title": "issue1", "createdAt": "2023-01-01T00:00:00Z"}]},
                            }
                        ],
                    }
                }
            }
        }
        mock_ql.make_ql_request.return_value.json.return_value = mock_response
        mock_ql.make_ql_request.return_value.status_code = 200

        variables = {"org": "test_org", "notification_issue_tag": "test_tag", "max_repos": 100, "cursor": "None"}

        result = get_repository_page(mock_logger, mock_ql, variables)

        assert result == mock_response

    @patch("github_api_toolkit.github_graphql_interface")
    @patch("logging.Logger")
    def test_get_repository_page_with_cursor(self, mock_logger, mock_ql):
        mock_response = {
            "data": {
                "organization": {
                    "repositories": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "end_cursor"},
                        "nodes": [
                            {
                                "name": "repo1",
                                "updatedAt": "2023-01-01T00:00:00Z",
                                "issues": {"nodes": [{"title": "issue1", "createdAt": "2023-01-01T00:00:00Z"}]},
                            }
                        ],
                    }
                }
            }
        }
        mock_ql.make_ql_request.return_value.json.return_value = mock_response
        mock_ql.make_ql_request.return_value.status_code = 200

        variables = {"org": "test_org", "notification_issue_tag": "test_tag", "max_repos": 100, "cursor": "some_cursor"}

        result = get_repository_page(mock_logger, mock_ql, variables)

        assert result == mock_response

    @patch("github_api_toolkit.github_graphql_interface")
    @patch("logging.Logger")
    def test_get_repository_page_failure(self, mock_logger, mock_ql):
        mock_ql.make_ql_request.side_effect = Exception("Request failed")

        variables = {"org": "test_org", "notification_issue_tag": "test_tag", "max_repos": 100, "cursor": "None"}

        with pytest.raises(Exception) as excinfo:
            get_repository_page(mock_logger, mock_ql, variables)

        assert "Request failed" in str(excinfo.value)


class TestCleanRepositories:
    def test_clean_repositories_with_none_values(self):
        repositories = [{"name": "repo1"}, None, {"name": "repo2"}, None]
        result = clean_repositories(repositories)
        assert result == [{"name": "repo1"}, {"name": "repo2"}]

    def test_clean_repositories_without_none_values(self):
        repositories = [{"name": "repo1"}, {"name": "repo2"}]
        result = clean_repositories(repositories)
        assert result == repositories

    def test_clean_repositories_all_none_values(self):
        repositories = [None, None, None]
        result = clean_repositories(repositories)
        assert result == []

    def test_clean_repositories_empty_list(self):
        repositories = []
        result = clean_repositories(repositories)
        assert result == []


class TestLogErrorRepositories:
    @patch("src.main.wrapped_logging")
    def test_log_error_repositories_with_errors(self, mock_logger):
        response_json = {"errors": ["error1", "error2"]}
        log_error_repositories(mock_logger, response_json)
        mock_logger.log_error.assert_called_once_with("Error repositories: ['error1', 'error2']")

    @patch("src.main.wrapped_logging")
    def test_log_error_repositories_without_errors(self, mock_logger):
        response_json = {"data": {"some_key": "some_value"}}
        log_error_repositories(mock_logger, response_json)
        mock_logger.log_error.assert_not_called()


class TestFilterResponse:
    @patch("src.main.wrapped_logging")
    def test_filter_response_success(self, mock_logger):
        response_json = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [
                            {"name": "repo1", "updatedAt": "2023-01-01T00:00:00Z"},
                            {"name": "repo2", "updatedAt": "2023-01-02T00:00:00Z"},
                        ]
                    }
                }
            }
        }
        result = filter_response(mock_logger, response_json)
        assert result == [
            {"name": "repo1", "updatedAt": "2023-01-01T00:00:00Z"},
            {"name": "repo2", "updatedAt": "2023-01-02T00:00:00Z"},
        ]

    @patch("src.main.wrapped_logging")
    def test_filter_response_with_none_values(self, mock_logger):
        response_json = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [
                            {"name": "repo1", "updatedAt": "2023-01-01T00:00:00Z"},
                            None,
                            {"name": "repo2", "updatedAt": "2023-01-02T00:00:00Z"},
                        ]
                    }
                }
            }
        }
        result = filter_response(mock_logger, response_json)
        assert result == [
            {"name": "repo1", "updatedAt": "2023-01-01T00:00:00Z"},
            {"name": "repo2", "updatedAt": "2023-01-02T00:00:00Z"},
        ]

    @patch("src.main.wrapped_logging")
    def test_filter_response_with_errors(self, mock_logger):
        response_json = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [
                            {"name": "repo1", "updatedAt": "2023-01-01T00:00:00Z"},
                            {"name": "repo2", "updatedAt": "2023-01-02T00:00:00Z"},
                        ]
                    }
                }
            },
            "errors": ["error1", "error2"],
        }
        result = filter_response(mock_logger, response_json)
        mock_logger.log_error.assert_called_once_with("Error repositories: ['error1', 'error2']")
        assert result == [
            {"name": "repo1", "updatedAt": "2023-01-01T00:00:00Z"},
            {"name": "repo2", "updatedAt": "2023-01-02T00:00:00Z"},
        ]


class TestGetEnvironmentVariables:
    @patch("src.main.get_environment_variable")
    def test_get_environment_variables_success(self, mock_get_env_var):
        mock_get_env_var.side_effect = [
            "mock_org",
            "mock_app_client_id",
            "mock_aws_default_region",
            "mock_aws_secret_name",
        ]

        result = get_environment_variables()

        assert result == ("mock_org", "mock_app_client_id", "mock_aws_default_region", "mock_aws_secret_name")
        mock_get_env_var.assert_has_calls(
            [call("GITHUB_ORG"), call("GITHUB_APP_CLIENT_ID"), call("AWS_DEFAULT_REGION"), call("AWS_SECRET_NAME")]
        )

    @patch("src.main.get_environment_variable")
    def test_get_environment_variables_failure(self, mock_get_env_var):
        mock_get_env_var.side_effect = Exception("Environment variable not found")

        with pytest.raises(Exception) as excinfo:
            get_environment_variables()

        assert "Environment variable not found" in str(excinfo.value)
        mock_get_env_var.assert_called_once_with("GITHUB_ORG")


class TestGetRepositories:
    @patch("src.main.get_repository_page")
    @patch("src.main.filter_response")
    @patch("src.main.wrapped_logging")
    def test_get_repositories_single_page(self, mock_logger, mock_filter_response, mock_get_repository_page):
        mock_logger_instance = mock_logger.return_value
        mock_response_json = {
            "data": {
                "organization": {
                    "repositories": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "end_cursor"},
                        "nodes": [
                            {
                                "name": "repo1",
                                "updatedAt": "2023-01-01T00:00:00Z",
                                "issues": {"nodes": [{"title": "issue1", "createdAt": "2023-01-01T00:00:00Z"}]},
                            }
                        ],
                    }
                }
            }
        }
        mock_get_repository_page.return_value = mock_response_json
        mock_filter_response.return_value = mock_response_json["data"]["organization"]["repositories"]["nodes"]

        archive_rules = {"notification_issue_tag": "test_tag"}
        ql = patch("github_api_toolkit.github_graphql_interface").start()

        result, number_of_pages = get_repositories(mock_logger_instance, ql, "test_org", archive_rules)

        assert result == mock_response_json["data"]["organization"]["repositories"]["nodes"]
        assert number_of_pages == 1
        mock_get_repository_page.assert_called_once()
        mock_filter_response.assert_called_once()

    @patch("src.main.get_repository_page")
    @patch("src.main.filter_response")
    @patch("src.main.wrapped_logging")
    def test_get_repositories_multiple_pages(self, mock_logger, mock_filter_response, mock_get_repository_page):
        mock_logger_instance = mock_logger.return_value
        mock_response_json_page_1 = {
            "data": {
                "organization": {
                    "repositories": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "end_cursor_1"},
                        "nodes": [
                            {
                                "name": "repo1",
                                "updatedAt": "2023-01-01T00:00:00Z",
                                "issues": {"nodes": [{"title": "issue1", "createdAt": "2023-01-01T00:00:00Z"}]},
                            }
                        ],
                    }
                }
            }
        }
        mock_response_json_page_2 = {
            "data": {
                "organization": {
                    "repositories": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "end_cursor_2"},
                        "nodes": [
                            {
                                "name": "repo2",
                                "updatedAt": "2023-01-02T00:00:00Z",
                                "issues": {"nodes": [{"title": "issue2", "createdAt": "2023-01-02T00:00:00Z"}]},
                            }
                        ],
                    }
                }
            }
        }
        mock_get_repository_page.side_effect = [mock_response_json_page_1, mock_response_json_page_2]
        mock_filter_response.side_effect = [
            mock_response_json_page_1["data"]["organization"]["repositories"]["nodes"],
            mock_response_json_page_2["data"]["organization"]["repositories"]["nodes"],
        ]

        archive_rules = {"notification_issue_tag": "test_tag"}
        ql = patch("github_api_toolkit.github_graphql_interface").start()

        result, number_of_pages = get_repositories(mock_logger_instance, ql, "test_org", archive_rules)

        expected_result = (
            mock_response_json_page_1["data"]["organization"]["repositories"]["nodes"]
            + mock_response_json_page_2["data"]["organization"]["repositories"]["nodes"]
        )

        assert result == expected_result
        assert number_of_pages == 2  # noqa: PLR2004
        assert mock_get_repository_page.call_count == 2  # noqa: PLR2004
        assert mock_filter_response.call_count == 2  # noqa: PLR2004

    @patch("src.main.get_repository_page")
    @patch("src.main.filter_response")
    @patch("src.main.wrapped_logging")
    def test_get_repositories_no_repositories(self, mock_logger, mock_filter_response, mock_get_repository_page):
        mock_logger_instance = mock_logger.return_value
        mock_response_json = {
            "data": {
                "organization": {
                    "repositories": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "end_cursor"},
                        "nodes": [],
                    }
                }
            }
        }
        mock_get_repository_page.return_value = mock_response_json
        mock_filter_response.return_value = []

        archive_rules = {"notification_issue_tag": "test_tag"}
        ql = patch("github_api_toolkit.github_graphql_interface").start()

        result, number_of_pages = get_repositories(mock_logger_instance, ql, "test_org", archive_rules)

        assert result == []
        assert number_of_pages == 1
        mock_get_repository_page.assert_called_once()
        mock_filter_response.assert_called_once()


class TestLoadArchiveRules:
    def test_load_archive_rules_success(self):
        archive_rules = {
            "archive_threshold": 365,
            "notification_period": 30,
            "notification_issue_tag": "archive-notice",
            "exemption_filename": "DO_NOT_ARCHIVE",
            "maximum_notifications": 5,
        }

        result = load_archive_rules(archive_rules)

        assert result == (365, 30, "archive-notice", "DO_NOT_ARCHIVE", 5)

    def test_load_archive_rules_missing_key(self):
        archive_rules = {
            "archive_threshold": 365,
            "notification_period": 30,
            "notification_issue_tag": "archive-notice",
            # "exemption_filename" is missing
            "maximum_notifications": 5,
        }

        with pytest.raises(Exception) as excinfo:
            load_archive_rules(archive_rules)

        assert "Key exemption_filename not found in the dictionary." in str(excinfo.value)

    def test_load_archive_rules_invalid_value(self):
        archive_rules = {
            "archive_threshold": "not_an_int",
            "notification_period": 30,
            "notification_issue_tag": "archive-notice",
            "exemption_filename": "DO_NOT_ARCHIVE",
            "maximum_notifications": 5,
        }

        with pytest.raises(ValueError):
            load_archive_rules(archive_rules)


class TestProcessRepositories:
    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_archiving(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {
                    "nodes": [
                        {
                            "title": "issue1",
                            "createdAt": (datetime.datetime.now() - datetime.timedelta(days=40)).strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                        }
                    ]
                },
            }
        ]
        archive_criteria = ["365", "30", "archive-notice", "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        mock_response = Response()
        mock_rest_instance.patch.return_value = mock_response

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 1
        assert issues_created == 0
        mock_rest_instance.patch.assert_called_once_with(f"/repos/{org}/repo1", {"archived": True})

    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_create_issue(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        # Make check for if the label exists successful
        mock_rest_instance.get.return_value.status_code = 200

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            }
        ]
        archive_criteria = ["365", "30", "archive-notice", "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        mock_response = Response()

        mock_rest_instance.post.return_value = mock_response

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 1
        mock_rest_instance.post.assert_called_once_with(
            f"/repos/{org}/repo1/issues",
            {
                "title": "Repository Archive Notice",
                "body": "This repository will be archived.",
                "labels": ["archive-notice"],
            },
        )

    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_skip_recent_update(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            }
        ]
        archive_criteria = ["365", "30", "archive-notice", "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 0
        mock_rest_instance.post.assert_not_called()
        mock_rest_instance.patch.assert_not_called()

    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_max_notifications(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        # Make check for if the label exists successful
        mock_rest_instance.get.return_value.status_code = 200

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo2",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo3",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo4",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo5",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo6",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
        ]
        archive_criteria = ["365", "30", "archive-notice", "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        mock_response = Response()
        mock_rest_instance.post.return_value = mock_response

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 5  # noqa: PLR2004
        assert mock_rest_instance.post.call_count == 5  # noqa: PLR2004
        mock_logger_instance.log_info.assert_called_with(
            "Maximum number of notifications reached. No more notifications will be made."
        )

    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_issue_not_meeting_notification_period(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {
                    "nodes": [
                        {
                            "title": "issue1",
                            "createdAt": (datetime.datetime.now() - datetime.timedelta(days=10)).strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                        }
                    ]
                },
            }
        ]
        archive_criteria = ["365", "30", "archive-notice", "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 0
        mock_rest_instance.post.assert_not_called()
        mock_rest_instance.patch.assert_not_called()

    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_issue_logging(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        # Make check for if the label exists successful
        mock_rest_instance.get.return_value.status_code = 200

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo2",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo3",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo4",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo5",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo6",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
            {
                "name": "repo7",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            },
        ]
        archive_criteria = ["365", "30", "archive-notice", "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        mock_response = Response()
        mock_rest_instance.post.return_value = mock_response

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 5  # noqa: PLR2004
        assert mock_rest_instance.post.call_count == 5  # noqa: PLR2004
        mock_logger_instance.log_info.assert_called_with(
            "Skipping repository. Maximum number of notifications reached."
        )

    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_issue_label_creation(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        # Make check for if the label exists successful
        mock_rest_instance.get.return_value = "404"

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            }
        ]

        notification_issue_tag = "archive-notice"

        archive_criteria = ["365", "30", notification_issue_tag, "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        mock_response = Response()
        mock_rest_instance.post.return_value = mock_response

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 1

        # Assert that there was 2 post requests for 1 repository
        # This means that the label was created and the issue was created
        assert mock_rest_instance.post.call_count == 2  # noqa: PLR2004

    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_issue_label_exists(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        # Make check for if the label exists successful
        mock_rest_instance.get.return_value.status_code = 200

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            }
        ]

        notification_issue_tag = "archive-notice"

        archive_criteria = ["365", "30", notification_issue_tag, "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        mock_response = Response()
        mock_rest_instance.post.return_value = mock_response

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 1

        # Assert that there was 1 post request for 1 repository
        # This means that the issue was created but not the label since it already exists
        assert mock_rest_instance.post.call_count == 1

    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_issue_label_creation_failed(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        # Make check for if the label exists successful
        mock_rest_instance.get.return_value = "404"

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            }
        ]

        notification_issue_tag = "archive-notice"

        archive_criteria = ["365", "30", notification_issue_tag, "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        mock_response = HTTPError()
        mock_rest_instance.post.return_value = mock_response

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 0

        # Assert that there was 1 post request for 1 repository
        # This means that the label creation failed and the issue was not created
        assert mock_rest_instance.post.call_count == 1

    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_issue_creation_failed(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        # Make check for if the label exists successful
        mock_rest_instance.get.return_value.status_code = 200

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {"nodes": []},
            }
        ]

        notification_issue_tag = "archive-notice"

        archive_criteria = ["365", "30", notification_issue_tag, "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        mock_response = HTTPError()
        mock_rest_instance.post.return_value = mock_response

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 0

        # Assert that there was 1 post request for 1 repository
        # This means that the issue creation failed
        assert mock_rest_instance.post.call_count == 1

    # test archive failure
    @patch("src.main.wrapped_logging")
    @patch("github_api_toolkit.github_interface")
    def test_process_repositories_archive_failure(self, mock_rest, mock_logger):
        mock_logger_instance = mock_logger.return_value
        mock_rest_instance = mock_rest.return_value

        interfaces = [mock_logger_instance, mock_rest_instance]
        org = "test_org"
        repositories = [
            {
                "name": "repo1",
                "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issues": {
                    "nodes": [{"title": "issue1", "createdAt": "2023-01-01T00:00:00Z"}]
                },  # Issue open for > 30 days
            }
        ]
        archive_criteria = ["365", "30", "archive-notice", "5"]
        notification_content = ["Repository Archive Notice", "This repository will be archived."]

        mock_response = HTTPError()
        mock_rest_instance.patch.return_value = mock_response

        repositories_archived, issues_created = process_repositories(
            interfaces, org, repositories, archive_criteria, notification_content
        )

        assert repositories_archived == 0
        assert issues_created == 0
        mock_rest_instance.patch.assert_called_once_with(f"/repos/{org}/repo1", {"archived": True})


class TestHandler:
    # The methods in this class exclude the linting check PLR0913.
    # This check limits the number of arguments a function can have.
    # The test for the handler function requires a large number of arguments as lots of mocking is required.
    # This is why the check is excluded for each method.

    @patch("src.main.get_config_file")
    @patch("src.main.get_dict_value")
    @patch("src.main.wrapped_logging")
    @patch("src.main.get_environment_variables")
    @patch("boto3.session.Session")
    @patch("src.main.get_access_token")
    @patch("github_api_toolkit.github_graphql_interface")
    @patch("github_api_toolkit.github_interface")
    @patch("src.main.get_repositories")
    @patch("src.main.load_archive_rules")
    @patch("src.main.process_repositories")
    def test_handler_success(  # noqa: PLR0913
        self,
        mock_process_repositories,
        mock_load_archive_rules,
        mock_get_repositories,
        mock_github_interface,
        mock_github_graphql_interface,
        mock_get_access_token,
        mock_boto3_session,
        mock_get_environment_variables,
        mock_wrapped_logging,
        mock_get_dict_value,
        mock_get_config_file,
    ):
        # Mocking the return values
        mock_get_config_file.return_value = {
            "features": {"show_log_locally": True},
            "archive_configuration": {"some_key": "some_value"},
        }
        mock_get_dict_value.side_effect = lambda d, k: d[k]
        mock_wrapped_logging.return_value = MagicMock()
        mock_get_environment_variables.return_value = (
            "mock_org",
            "mock_app_client_id",
            "mock_aws_default_region",
            "mock_aws_secret_name",
        )
        mock_boto3_session.return_value.client.return_value = MagicMock()
        mock_get_access_token.return_value = ("mock_token", "mock_other_value")
        mock_github_graphql_interface.return_value = MagicMock()
        mock_github_interface.return_value = MagicMock()
        mock_get_repositories.return_value = (["repo1", "repo2"], 1)
        mock_load_archive_rules.return_value = (365, 30, "archive-notice", "DO_NOT_ARCHIVE", 5)
        mock_process_repositories.return_value = (1, 1)

        # Call the handler function
        result = handler({}, {})

        # Assertions
        assert result == "Script completed. 2 repositories checked. 1 issues created. 1 repositories archived."
        mock_get_config_file.assert_called_once_with("./config/config.json")
        mock_get_dict_value.assert_any_call(mock_get_config_file.return_value, "features")
        mock_get_dict_value.assert_any_call(mock_get_config_file.return_value, "archive_configuration")
        mock_wrapped_logging.assert_called_once_with(True)
        mock_get_environment_variables.assert_called_once()
        mock_boto3_session.return_value.client.assert_called_once_with(
            service_name="secretsmanager", region_name="mock_aws_default_region"
        )
        mock_get_access_token.assert_called_once_with(
            mock_boto3_session.return_value.client.return_value,
            "mock_aws_secret_name",
            "mock_org",
            "mock_app_client_id",
        )
        mock_github_graphql_interface.assert_called_once_with("mock_token")
        mock_github_interface.assert_called_once_with("mock_token")
        mock_get_repositories.assert_called_once_with(
            mock_wrapped_logging.return_value,
            mock_github_graphql_interface.return_value,
            "mock_org",
            {"some_key": "some_value"},
        )
        mock_load_archive_rules.assert_called_once_with({"some_key": "some_value"})
        mock_process_repositories.assert_called_once_with(
            [mock_wrapped_logging.return_value, mock_github_interface.return_value],
            "mock_org",
            ["repo1", "repo2"],
            ["365", "30", "archive-notice", "5"],
            [
                "Repository Archive Notice",
                "## Important Notice \n\nThis repository has not been updated in over 365 days and will be archived in 30 days if no action is taken. \n## Actions Required to Prevent Archive \n\n1. Update the repository by creating/updating a file called `DO_NOT_ARCHIVE`. \n   - This file should contain the reason why the repository should not be archived. \n   - If the file already exists, please update it with the latest information. \n2. Close this issue. \n\nAfter these actions, the repository will be exempt from archive for another 365 days. \n\nIf you have any questions, please contact an organization administrator.",
            ],
        )

    @patch("src.main.get_config_file")
    @patch("src.main.get_dict_value")
    @patch("src.main.wrapped_logging")
    @patch("src.main.get_environment_variables")
    @patch("boto3.session.Session")
    @patch("src.main.get_access_token")
    @patch("github_api_toolkit.github_graphql_interface")
    @patch("github_api_toolkit.github_interface")
    @patch("src.main.get_repositories")
    @patch("src.main.load_archive_rules")
    @patch("src.main.process_repositories")
    def test_handler_failure(  # noqa PLR0913
        self,
        mock_process_repositories,
        mock_load_archive_rules,
        mock_get_repositories,
        mock_github_interface,
        mock_github_graphql_interface,
        mock_get_access_token,
        mock_boto3_session,
        mock_get_environment_variables,
        mock_wrapped_logging,
        mock_get_dict_value,
        mock_get_config_file,
    ):
        # Mocking the return values
        mock_get_config_file.side_effect = Exception("Configuration file not found")

        # Call the handler function
        with pytest.raises(Exception) as excinfo:
            handler({}, {})

        # Assertions
        assert "Configuration file not found" in str(excinfo.value)
        mock_get_config_file.assert_called_once_with("./config/config.json")
        mock_get_dict_value.assert_not_called()
        mock_wrapped_logging.assert_not_called()
        mock_get_environment_variables.assert_not_called()
        mock_boto3_session.assert_not_called()
        mock_get_access_token.assert_not_called()
        mock_github_graphql_interface.assert_not_called()
        mock_github_interface.assert_not_called()
        mock_get_repositories.assert_not_called()
        mock_load_archive_rules.assert_not_called()
        mock_process_repositories.assert_not_called()


class TestHandleResponse:
    @patch("src.main.wrapped_logging")
    def test_handle_response_valid_response(self, mock_logger):
        mock_response = Response()
        message = "Error message"

        result = handle_response(mock_logger, mock_response, message)

        assert result is True
        mock_logger.log_error.assert_not_called()

    @patch("src.main.wrapped_logging")
    def test_handle_response_invalid_response(self, mock_logger):
        mock_response = "Invalid response"
        message = "Error message"

        result = handle_response(mock_logger, mock_response, message)

        assert result is False
        mock_logger.log_error.assert_called_once_with(message)

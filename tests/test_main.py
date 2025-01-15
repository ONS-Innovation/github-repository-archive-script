import json
import os
from unittest.mock import call, mock_open, patch

import pytest

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
    load_archive_rules,
    log_error_repositories,
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

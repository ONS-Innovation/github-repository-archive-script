import json
import os
from unittest.mock import call, mock_open, patch

import pytest

from src.main import (
    get_access_token,
    get_config_file,
    get_dict_value,
    get_environment_variable,
    get_repository_page,
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

import pytest

@pytest.fixture
def environment_lookup():
    values = {
        ("CREATE_GITHUB_ISSUES", "false"): "true",
        ("ENABLE_ARCHIVING", "false"): "true",
        ("GITHUB_ORG", None): "mock_org",
        ("GITHUB_APP_CLIENT_ID", None): "mock_app_client_id",
        ("AWS_DEFAULT_REGION", None): "mock_aws_default_region",
        ("AWS_SECRET_NAME", None): "mock_aws_secret_name",
    }
    return lambda name, default=None: values[(name, default)]
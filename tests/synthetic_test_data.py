import datetime

mock_repositories = [
    # Test case: repository updated in past year, i.e. still active
    {
        "name": "test_repo1",
        "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issues": {"nodes": []},
    },
    # Test case: repository not updated in past year, no open issues
    {
        "name": "test_repo2",
        "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issues": {"nodes": []},
    },
    # Test case: repository not updated in past year, issue open for < 30 days
    {
        "name": "test_repo3",
        "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issues": {
            "nodes": [
                {
                    "title": "test_issue1",
                    "createdAt": (datetime.datetime.now() - datetime.timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            ]
        },
    },
    # Test case: repository not updated in past year, issue open for > 30 days
    {
        "name": "test_repo4",
        "updatedAt": (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issues": {
            "nodes": [
                {
                    "title": "test_issue1",
                    "createdAt": (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            ]
        },
    },
]
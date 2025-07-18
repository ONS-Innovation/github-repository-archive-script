# The Process

## Steps in the Process

### 1. Data Collection

Using the GitHub API, collect all non-archived repositories for a given organisation (ONSdigital).

This includes the repository's name, when it was last updated and the number of open issues with the notification issue label (defined within the configuration - see [Configuration](./configuration.md)).

### 2. Data Processing

Iterate through each repository and check the following:

#### a. Last Updated

Has the repository been updated in the last year? If not, it is considered inactive and is eligible for archiving.

(The time period can be configured in the [Configuration](./configuration.md) file.)

Checking for updates allows the exemption mechanism to work. If an exemption file gets added or updated within the repository, it will have been updated and considered active.

#### b. Open Issues

If the repository is eligible for archiving, check if there is an open issue with the notification label.

If there is no such issue, create one to notify the team that the repository is being archived.

#### c. Archive Repository

If there is an open issue with the notification label, check how long the issue has been open.

If the issue has been open for more than 30 days (configurable in the [Configuration](./configuration.md) file), archive the repository.

## Process Flow Chart

![Process Flow Chart](../assets/images/archive_tool_process.drawio.png)

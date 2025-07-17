# Configuration

The archive tool uses both a local and cloud configuration file to manage its settings. The local configuration file is located within `./config/config.json`. The cloud configuration file is stored in an S3 bucket and is used as a way to adjust the settings of the archive tool without needing to modify the local file and redeploy the application.

## `config.json`

The `config.json` file contains the following:

```json
{
  "features": {
    "show_log_locally": false,
    "use_local_config": false
  },
  "archive_configuration": {
    "archive_threshold": 365,
    "notification_period": 30,
    "notification_issue_tag": "Archive Notice",
    "exemption_filename": ["ArchiveExemption.txt", "ArchiveExemption.md"],
    "maximum_notifications": 1
  }
}
```

### `features` Section

This section contains feature flags that control which the tool's features are enabled or disabled.

#### `show_log_locally`

If set to `true`, the tool will output logs to a `debug.log` file at the root of the project directory. This is useful for debugging purposes. If set to `false`, logs will not be saved locally.

When deploying to AWS, this should be set to `false` to avoid files being written to the local filesystem.

#### `use_local_config`

If set to `true`, the tool will use the local configuration file (`config.json`) for its settings (overriding any cloud configuration). If set to `false`, the tool will fetch the configuration from the cloud (S3 bucket).

**When deploying to AWS, this must be set to `false` to ensure the tool uses the cloud configuration.** Pulling the configuration from the cloud allows for dynamic updates without needing to redeploy the application.

When debugging locally, you can set this to `true` to use the local configuration file. This is useful if you need to see the logs locally, without affecting the cloud deployment.

### `archive_configuration` Section

This section contains the configuration settings related to the archiving process, including thresholds and notification settings.

#### `archive_threshold`

This is the number of days which a repository must be inactive before it is considered for archiving. The default value is `365` days (1 year).

#### `notification_period`

This is the number of days that a notification issue will be open before the repository is archived. The default value is `30` days.

#### `notification_issue_tag`

This is the tag that will be applied to the notification issue created for a repository that is eligible for archiving. The default value is `"Archive Notice"`.

This should not be changed as the label has been used across the GitHub organisation already. The label allows us to programatically identify repositories that the tool has been run against.

#### `exemption_filename`

This is an array of filenames that the exemption files are recommended to be named. This list is used directly when generating the body of the notification issue. The default values are `["ArchiveExemption.txt", "ArchiveExemption.md"]`.

The exemption file itself is not currently used by the tool, but may be used in the future. This is further explained in the [Exemption File](./exemption_file.md) documentation.

#### `maximum_notifications`

This is the maximum number of notifications that can be created by the tool in a single run. When running the tool locally, this should be set to either `1` or `0` to avoid creating too many notifications during testing.

When deploying to AWS, this should be set to a higher value, currently `200`, to allow the tool to process a good volume of repositories in a single run.

### Example During Local Testing

When testing locally, you might set the `config.json` file as follows:

```json
{
  "features": {
    "show_log_locally": true,
    "use_local_config": true
  },
  "archive_configuration": {
    "archive_threshold": 365,
    "notification_period": 30,
    "notification_issue_tag": "Archive Notice",
    "exemption_filename": ["ArchiveExemption.txt", "ArchiveExemption.md"],
    "maximum_notifications": 0
  }
}
```

This will ensure that the local configuration is used, logs are saved to `debug.log`, and no notifications are created during testing.

### Example On AWS

When deploying to AWS, the `config.json` file should be set as follows:

```json
{
  "features": {
    "show_log_locally": false,
    "use_local_config": false
  },
  "archive_configuration": {
    "archive_threshold": 365,
    "notification_period": 30,
    "notification_issue_tag": "Archive Notice",
    "exemption_filename": ["ArchiveExemption.txt", "ArchiveExemption.md"],
    "maximum_notifications": 200
  }
}
```

This configuration ensures that the tool uses the cloud configuration, does not save logs locally, and can process a larger number of repositories in a single run.

If `use_local_config` is set to `false`, the tool will fetch the configuration from the cloud S3 bucket. This file can be tuned to the needs of the Technical Advisory Group (TAG) and will rarely need to be changed.

**It is essential that `use_local_config` is set to `false` when deploying to AWS.** 

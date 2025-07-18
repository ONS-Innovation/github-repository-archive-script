# Exemption Process

In order to make a repository exempt from the archive process, a push or update must be made to the repository. We recommend doing this by creating/updating an exemption file in the repository. Each push to the repository will make the repository exempt from the archive process for a year (this value is configurable).

## Exemption File

The name of the exemption file can be configured within `config.json`. For more information on the tool's configuration, refer to the [Configuration Documentation](./configuration.md).

It is advised to the users within the notification issue that the file should be named according to the configured exemption file names and placed in the root of the repository. We also recommend that the file contains a comment indicating the reason for the exemption.

The exemption file itself does not impact the tool's functionality in any way, but only acts as a clean way to push an update to the repository, which will reset the exemption timer.

In the future, there might be some scope to report on the exemption files, such as listing repositories that have an exemption file, checking their age, or providing insights into why repositories are exempted. However, this is not currently implemented.

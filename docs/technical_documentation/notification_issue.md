# Notification Issue

When a repository is eligible for archiving (i.e. it has not been updated in the last year), an issue is created in the repository to notify owners/maintainers. This issue serves as a reminder and provides information on how to archive the repository or make it exempt from the process if desired.

All created issues are given an `Archive Notice` label to easily identify them. 

## Issue Contents

The notification issue contains the following information:

- How long the repository has until it will be archived.
- How to prevent the repository from being archived by creating or updating an exemption file.
- How the exemption file should be named and what it should contain.
- How users can manually archive the repository if they choose to do so.

## Changing the Notification Issue

To change the contents of the issue, code changes within `src/main.py` are required:

- **Notification Issue Title**: To change the title of the notification issue, modify the `notification_issue_title` variable in `src/main.py`.
- **Notification Issue Body**: To change the body of the notification issue, modify the `notification_issue_body_tuple` variable in `src/main.py`. This tuple gets joined into a single string with line breaks, so you can format it as needed.

See an example snippet below:

```python
notification_issue_title = "Repository Archive Notice"

notification_issue_body_tuple = (
    "## Important Notice \n\n",
    f"This repository has not been updated in over {archive_threshold} days and will be archived in {notification_period} days if no action is taken. \n",
    "## Actions Required to Prevent Archive \n\n",
    "1. Update the repository by creating/updating an exemption file. \n",
    "   - The exemption file should be named one of the following: \n",
    f"{''.join(formatted_filenames)}\n",
    "   - This file should contain the reason why the repository should not be archived. \n",
    "   - If the file already exists, please update it with the latest information. \n",
    "2. Close this issue. \n\n",
    f"After these actions, the repository will be exempt from archive for another {archive_threshold} days. \n\n",
    "## Manual Archive \n\n",
    "If you wish to archive this repository manually, please ensure the following: \n",
    "1. A notice is added to the repository `README.md` file indicating that the repository is archived. \n",
    "2. All issues and pull requests are closed (Optional but strongly recommended). \n",
    "3. Repository Admins / CODEOWNERS are up to date before archiving. This will make it easier to unarchive the repository in the future if needed. \n\n",
    "After these actions, you can archive the repository by going to the repository settings and selecting 'Archive this repository'. \n\n",
)
```

**Please Note:** The above code snippet is only an example and might not be the exact code in your `src/main.py`. 

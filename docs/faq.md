# Frequently Asked Questions (FAQs)

## How does the Archive Process Work?

- Each week, the archive tool will process each non-archived repository within ONSdigital.
- For each repository, it will:
  - Check if the repository hasn't been updated within the last year.
  - If it hasn't been updated, it will create an issue in the repository to notify the maintainers. The issue will include details about how to avoid the repository being archived and how to archive the repository manually.
  - If an issue already exists for the repository, it will check how long ago the issue was created.
  - If the issue was created more than 30 days ago, the tool will archive the repository.

In depth information on this process is available within the [Technical Documentation](./technical_documentation/the_process.md).

## How Can I Prevent My Repository from Being Archived?

To prevent your repository from being archived, you should push an update to the repository at least once a year. We recommend that an `ArchiveExemption.txt` or `ArchiveExemption.md` file is added to the root of the repository to indicate that it should not be archived. This file should contain a brief explanation of why the repository is still relevant and should not be archived.

This file will need to be updated annually to ensure that the repository remains exempt from archiving. If you do not update this file, the repository will be archived after a year of inactivity.

## What Happens if My Repository is Archived?

When a repository is archived, it becomes read-only. This means that no further changes can be made to the repository, including issues or pull requests. The repository can still be viewed for reference, including any open issues or pull requests that were present at the time of archiving. If you need to make changes to an archived repository, you will need to unarchive it first.

## How Do I Unarchive a Repository?

In order to unarchive a repository, you need to have administrative access to the repository either being an organisation or repository owner. You can unarchive a repository by going to the repository settings and selecting the "Unarchive" option.

To avoid the repository from being archived again, ensure that you push an update to the repository. This will make it exempt from archiving for another year. You may also want to add an `ArchiveExemption.txt` or `ArchiveExemption.md` file to the root of the repository to indicate that it should not be archived in the future.

It is important to note that if a repository is without an owner or has no active admin users, an organisation admin will need to unarchive the repository.

All repositories within ONSdigital should be maintained to have an up-to-date `CODEOWNERS` file and repository admins to ensure that access is available for unarchiving when necessary. This is specified within ONS' GitHub Usage Policy and must be adhered to.

## Can I Archive My Own Repository?

We encourage repository owners to archive their own repositories if they are no longer actively maintained or relevant. You can do this by going to the repository settings and selecting the "Archive" option. We recommend that you also add a notice to the repository's README file to inform users that the repository is archived and no longer maintained, along with closing any open issues or pull requests. This helps us align with GitHub's recommended practices for archiving repositories.

# Further Questions

For any further questions or concerns regarding the archiving process, please create an issue in the [Archive Tool repository](https://github.com/ONS-Innovation/github-repository-archive-script/issues) or contact an ONSdigital Owner.

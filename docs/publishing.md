# Publishing

## Source repository

Publish only the Workbench source tree. If it lives inside a larger repository,
export this subtree into a new directory and initialize a separate Git repository
there. Pushing the enclosing repository can expose unrelated files and history.
Check `git rev-parse --show-toplevel` before configuring a public remote.

For an existing standalone checkout, a source snapshot can be created with:

```sh
git archive --format=tar.gz --prefix=AFM-Workbench/ \
  --output=AFM-Workbench-github.tar.gz HEAD
```

For a project nested in another repository, run the archive command from the
enclosing repository's root and select the project tree explicitly instead of
`HEAD`, for example `HEAD:relative/path/to/afm-workbench`. Running that tree
selection from the nested directory can produce an empty archive. Run this after
committing the reviewed changes. Git archives include tracked source only and
do not include Git history. Inspect the archive before publishing it.

The new repository root should contain `README.md`, `LICENSE`, `pyproject.toml`,
`afm_workbench/`, `native/`, `scripts/`, `tests/` and `.github/workflows/check.yml`.
Keep `.gitignore`; do not add experimental TIFFs, local catalogs, environments,
test artifacts or generated native binaries. The committed reference fixture
contains generated synthetic results.

From the exported checkout, follow [installation](../README.md#run), audit the
[test catalog](testing.md), build the native backend, and run the full checks.
CI runs the Python checks on Mac and Linux; browser and desktop checks require
their separately documented dependencies. Preserve failed, skipped and legacy
results in the release record. Source publication does not establish scientific
validation or support on an untested platform.

## Desktop binaries

Build on the target OS and collect the sources and notices for the exact native
dependencies distributed, following the [native instructions](../native/README.md).
Stage new source files before running `python scripts/build.py`. Distribute the
matching `dist/AFM-Workbench-source.tar.gz` with the application. This archive
includes the native corresponding-source collection and is different from the
small GitHub source snapshot above.

Run the full [release checks](testing.md) against the rebuilt executable and
check the archive contents, bundled notices and signatures. The local Mac build
uses an ad-hoc signature; Developer ID signing, notarization and installation on
a clean Mac remain release gates. Windows native build and packaging remain
unvalidated. See [validation status](validation.md) for the evidence actually
recorded, including current browser coverage gaps.

# Human Hours public-doc changes

The files under `docs/` are public legal and support content.
They are protected by a trusted base-branch verifier because pull request code must not be allowed to redefine its own disclosure contract.

## Required repository rule

Require pull requests for `main` and require the `docs/trusted-content` commit status from the GitHub Actions app.
Require branches to be up to date before merging, block direct pushes, and grant no routine bypass.
These settings force a new candidate status after the trusted base changes.
The `pull_request_target` workflow publishes that status on the exact pull request head SHA after parsing candidate documents strictly as untrusted data.
Do not treat the candidate-controlled `docs-tooling` workflow as a replacement for the trusted status.

This status is safe only under the repository's single-writer model, where every untrusted contributor submits from a fork and no untrusted pull request author has repository write access.
Fork pull request tokens cannot write statuses, while the sole trusted writer is already an administrative trust root.
Do not grant repository write access to an untrusted pull request author while this control uses the ordinary GitHub Actions token.
Before adding another writer, replace this status with a dedicated GitHub App or an organization-enforced required workflow whose identity and definition candidate workflows cannot reuse.
`CODEOWNERS` routes every change to the sole trusted writer for review, but the branch rule must not require formal code-owner approval while that writer also authors repository pull requests because GitHub does not allow authors to approve their own pull requests.
If another trusted reviewer is added later, enable required code-owner approval only after the status source has also moved to a dedicated identity.

## Bootstrap

The first pull request that introduces `CODEOWNERS`, the trusted workflow, and the verifier cannot protect itself because those trust roots do not yet exist on the default branch.
This one-time bootstrap keeps the exact legacy document pair published while accepting either that complete pair or the exact proposed replacement pair.
It never accepts a mixture of legacy and proposed pages.
Review and merge the bootstrap pull request manually before enabling the required status and before merging any disclosure-content pull request.
After the bootstrap is on `main`, update or reopen the draft disclosure-content pull request once so the trusted workflow publishes `docs/trusted-content` and GitHub offers the GitHub Actions app as its expected source.
Then configure the repository rule described above, rebase or recreate the disclosure-content pull request on the protected base, update its head again, and confirm a fresh `docs/trusted-content` status protects that exact head SHA before merge.
Remove the retired legacy pair from the verifier immediately after the proposed pair is published so later changes use the normal staged migration below.

## Changing published content

The verifier pins every reviewed page by SHA-256 in addition to checking exact platform facts, links, metadata, styles, and repository structure.
A legitimate page change therefore needs a staged trust migration.

1. Open a verifier-only pull request that keeps the published page valid while temporarily accepting both the old complete contract and the proposed new complete contract.
2. Merge that verifier migration after manual trust-root review and all existing checks pass.
3. Open the page-content pull request and confirm that `docs/trusted-content` succeeds on its head SHA.
4. Remove the retired contract in the page-content pull request or in an immediate cleanup pull request, while keeping the newly published page valid.

Never execute candidate scripts, actions, generated files, or executables in the `pull_request_target` workflow.
The explicit unsafe-checkout opt-in is permitted only for the sparse `docs/` checkout because those bytes are consumed solely by the trusted parser.

## Local verification

Run these commands before pushing either stage:

```sh
python3 tests/test_verify_docs.py -v
python3 scripts/verify_docs.py
```

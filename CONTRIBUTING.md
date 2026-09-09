# Contributing

Use a fresh Python 3.11+ virtual environment, install with `python -m pip install .`,
then run `python -I -m unittest discover -s tests -v` and
`python scripts/make_cache_lab_fixtures.py --check`. Tests import the installed
package rather than adding the source checkout to Python's import path.

Keep fixtures synthetic and include the recipe. Do not submit production prompts,
credentials, URLs carrying access tokens, or user traces. A `SANITIZED` declaration
does not grant redistribution rights. Parser changes require regression coverage.
Preserve raw-byte and normalized-content hashes, adverse results, and explicit
accounting exclusions.

Identify any third-party source, dependency, data, prose or asset in a contribution
and its license before proposing inclusion. Do not present a known baseline as a
novel invention. New serving, GPU, routing, shared-memory reclamation or drift-control
features require an updated feature-level IP review before distribution.

For a rights concern, contact the repository owner through the hosting platform
or open an issue identifying the affected file/version and the claimed work or
patent. Do not post private documents or personal data. Maintainers should assess
the concrete claim and stop distributing an affected contribution while its
rights remain unresolved.

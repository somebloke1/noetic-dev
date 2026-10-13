# Testing from a fresh source checkout

CI prepares Python 3.12 build tools and Node 24, then builds the real Telos factory
from the public Telos revision `a8f6c253bb091562a9982b22217ebc4e78b1aa5b`.
The two test-bearing jobs share `.github/actions/test-prerequisites/action.yml`.
This fixture is independent of the installed product and author checkout.

For the same local preparation, run these commands from the Noetic source root
with Python, pip, venv support, Git, npm and Node 24 available:

```sh
python3 -m pip install 'setuptools>=68' wheel
telos_test_source=../noetic-test-telos
git clone --no-checkout https://github.com/somebloke1/telos.git "$telos_test_source"
git -C "$telos_test_source" checkout --detach a8f6c253bb091562a9982b22217ebc4e78b1aa5b
npm ci --prefix "$telos_test_source" --no-audit --no-fund
export NOETIC_TELOS_SOURCE="$(realpath "$telos_test_source")"
python3 -m scripts.noetic goal bundle --source "$NOETIC_TELOS_SOURCE" --output .runtime/components/telos-core.mjs
python3 scripts/validate_repo.py
python3 -m unittest discover -s tests -v
```

Use an isolated Python environment when the system Python restricts package
installation. The generated bundle and manifest are test inputs under the ignored
`.runtime` directory; source and installed component histories remain distinct.
Release fixtures use their own temporary directories and private installations.
The development-tool tests participate in default discovery through their package
marker. Model requests in helper tests use disposable mocks.

The actual native Opermem executable pair and optional live genus integration
require their separately documented explicit test configuration. Their absence
produces reported skips, not evidence of those integrations passing. CI does not
start local inference models or supply provider credentials.

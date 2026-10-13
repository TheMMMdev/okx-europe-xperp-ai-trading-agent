# Quant Agent EU

This distribution is English-only. See the authoritative [README.md](README.md) for installation, OKX Europe X-Perp support, security controls, risk defaults, referral disclosure, and known limitations.

Quant Agent EU is an independent derivative of the MIT-licensed AstraQuant project. It is not endorsed by OKX, does not provide financial advice, and does not guarantee profitability.

## Code structure entry

The repository never contained `OPENCODE.md`; references to that non-existent file are incorrect. Use these maintained maps instead:

| Document | Purpose |
|---|---|
| `astra_backend/README.md` | Backend layering and API boundaries |
| `scripts/README.md` | Runtime scripts, daemons, and operational entry points |
| `frontend/src/components/admin/README.md` | Frontend components and state ownership |

The documentation gates include `tests/audit/test_directory_docs_current.py` and `tests/core/test_readme_baseline_numbers.py`. Python package inventories are maintained through their relevant `__init__.py` files.

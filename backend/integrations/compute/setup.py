"""Pre-flight check for 0G Compute integration.

Run with:  python -m integrations.compute.setup

Verifies: Node.js version, npm deps, wallet balance, provider discovery,
provider acknowledgment, and sub-account funding.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_BRIDGE_DIR = Path(__file__).resolve().parent
_BRIDGE_SCRIPT = _BRIDGE_DIR / "_broker_bridge.mjs"
_MIN_NODE_VERSION = 22


def _run_bridge(args: list[str]) -> dict | list:
    """Run a CLI command on the broker bridge and return parsed JSON."""
    result = subprocess.run(
        ["node", str(_BRIDGE_SCRIPT), *args],
        cwd=str(_BRIDGE_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        try:
            err = json.loads(stderr)
            raise RuntimeError(err.get("error", stderr))
        except json.JSONDecodeError:
            raise RuntimeError(stderr or f"Bridge command failed: {args}")
    return json.loads(result.stdout)


def _print_step(label: str, ok: bool, detail: str = "") -> None:
    status = "OK" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)


def main() -> None:
    print("0G Compute — pre-flight check\n")
    errors: list[str] = []

    # 1. Node.js version
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version_str = result.stdout.strip()
        match = re.match(r"v?(\d+)", version_str)
        major = int(match.group(1)) if match else 0
        if major < _MIN_NODE_VERSION:
            _print_step("Node.js", False, f"{version_str} (need >= {_MIN_NODE_VERSION})")
            errors.append(f"Node.js >= {_MIN_NODE_VERSION} required. Install from https://nodejs.org")
        else:
            _print_step("Node.js", True, version_str)
    except FileNotFoundError:
        _print_step("Node.js", False, "not found")
        errors.append("Node.js not installed. Install from https://nodejs.org")

    if errors:
        print("\n" + "\n".join(f"  ! {e}" for e in errors))
        sys.exit(1)

    # 2. NPM deps
    node_modules = _BRIDGE_DIR / "node_modules"
    if not node_modules.exists():
        print("  [..] Installing npm dependencies...")
        r = subprocess.run(
            ["npm", "install"],
            cwd=str(_BRIDGE_DIR),
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            _print_step("npm install", False, r.stderr.strip()[:200])
            errors.append("npm install failed. Check integrations/compute/package.json")
            print("\n" + "\n".join(f"  ! {e}" for e in errors))
            sys.exit(1)
    _print_step("npm deps", True)

    # 3. Main account balance (auto-create ledger account if needed)
    try:
        bal = _run_bridge(["balance"])
        main_avail = float(bal.get("main", {}).get("available", "0"))
        main_total = float(bal.get("main", {}).get("total", "0"))
        if main_avail <= 0:
            _print_step("Main balance", False, f"{main_avail} 0G")
            errors.append("Wallet has no 0G tokens. Fund via https://faucet.0g.ai")
        else:
            _print_step("Main balance", True, f"{main_avail} 0G available ({main_total} total)")
    except Exception as exc:
        msg = str(exc)
        if "does not exist" in msg.lower() or "add-account" in msg.lower():
            print("  [..] Ledger account not found — creating via deposit (min 3 0G)...")
            try:
                _run_bridge(["deposit", "3"])
                _print_step("Initial deposit", True, "3 0G (account created)")
                bal = _run_bridge(["balance"])
                main_avail = float(bal.get("main", {}).get("available", "0"))
                main_total = float(bal.get("main", {}).get("total", "0"))
                _print_step("Main balance", True, f"{main_avail} 0G available ({main_total} total)")
            except Exception as exc2:
                _print_step("Account creation", False, str(exc2)[:200])
                errors.append(f"Account creation failed: {exc2}")
        else:
            _print_step("Main balance", False, msg[:200])
            errors.append(f"Balance check failed: {exc}")

    if errors:
        print("\n" + "\n".join(f"  ! {e}" for e in errors))
        sys.exit(1)

    # 4. Provider discovery
    providers = []
    try:
        providers = _run_bridge(["discover"])
        tee_providers = [p for p in providers if p.get("teeVerified")]
        _print_step(
            "Provider discovery",
            True,
            f"{len(providers)} providers ({len(tee_providers)} TEE-verified)",
        )
        if not providers:
            errors.append("No chatbot providers found on 0G network")
    except Exception as exc:
        _print_step("Provider discovery", False, str(exc)[:200])
        errors.append(f"Discovery failed: {exc}")

    if errors:
        print("\n" + "\n".join(f"  ! {e}" for e in errors))
        sys.exit(1)

    # Pick best provider (TEE-verified first)
    tee = [p for p in providers if p.get("teeVerified")]
    selected = tee[0] if tee else providers[0]
    addr = selected["address"]
    model = selected.get("model", "?")
    endpoint = selected.get("endpoint", "?")

    # 5. Provider metadata — verify endpoint reachable
    try:
        meta = _run_bridge(["metadata", addr])
        endpoint = meta.get("endpoint", endpoint)
        model = meta.get("model", model)
        # Quick reachability check
        import httpx
        r = httpx.get(endpoint, timeout=5, follow_redirects=True)
        _print_step("Provider endpoint", True, f"{endpoint} (HTTP {r.status_code})")
    except Exception as exc:
        _print_step("Provider endpoint", False, f"{endpoint} — {exc}")
        # Non-fatal: endpoint might only accept POST

    # 6. Provider acknowledgment
    try:
        _run_bridge(["acknowledge", addr])
        _print_step("Provider acknowledged", True, addr[:16] + "...")
    except Exception as exc:
        msg = str(exc)
        if "already" in msg.lower():
            _print_step("Provider acknowledged", True, "already done")
        else:
            _print_step("Provider acknowledged", False, msg[:200])
            errors.append(f"Acknowledgment failed: {msg}")

    # 7. Sub-account funding
    try:
        sub_bal = _run_bridge(["balance", addr])
        sub = sub_bal.get("sub")
        if sub and float(sub.get("balance", "0")) > 0:
            _print_step("Sub-account", True, f"{sub['balance']} 0G for {addr[:16]}...")
        else:
            _print_step("Sub-account", False, "unfunded")
            errors.append(
                f"Provider sub-account unfunded. Run:\n"
                f"    node integrations/compute/_broker_bridge.mjs transfer {addr} 0.01"
            )
    except Exception as exc:
        _print_step("Sub-account", False, str(exc)[:200])
        errors.append(f"Sub-account check failed: {exc}")

    # Summary
    print()
    if errors:
        print("Issues found:")
        for e in errors:
            print(f"  ! {e}")
        sys.exit(1)
    else:
        print(
            f"0G Compute ready\n"
            f"  provider: {addr}\n"
            f"  model:    {model}\n"
            f"  endpoint: {endpoint}\n"
            f"  main:     {main_avail} 0G\n"
            f"  sub:      {sub['balance'] if sub else '?'} 0G"
        )


if __name__ == "__main__":
    main()

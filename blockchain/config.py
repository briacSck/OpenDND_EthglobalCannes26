"""Hedera testnet client configuration."""

import os
from dotenv import load_dotenv
from hiero_sdk_python import Network, Client, AccountId, PrivateKey

load_dotenv()

_client: Client | None = None
_operator_id: AccountId | None = None
_operator_key: PrivateKey | None = None


def get_client() -> Client:
    """Return the singleton Hedera client, configured for testnet."""
    global _client, _operator_id, _operator_key
    if _client is not None:
        return _client

    network_name = os.getenv("HEDERA_NETWORK", "testnet")
    network = Network(network_name)
    _client = Client(network)

    # Accept both naming conventions (blockchain/ and config.py)
    account_id = os.getenv("HEDERA_OPERATOR_ID") or os.environ["HEDERA_ACCOUNT_ID"]
    private_key = os.getenv("HEDERA_OPERATOR_KEY") or os.environ["HEDERA_PRIVATE_KEY"]

    _operator_id = AccountId.from_string(account_id)
    _operator_key = PrivateKey.from_string(private_key)
    _client.set_operator(_operator_id, _operator_key)

    return _client


def get_operator_id() -> AccountId:
    """Return the operator AccountId (ensures client is initialized)."""
    get_client()
    assert _operator_id is not None
    return _operator_id


def get_operator_key() -> PrivateKey:
    """Return the operator PrivateKey (ensures client is initialized)."""
    get_client()
    assert _operator_key is not None
    return _operator_key

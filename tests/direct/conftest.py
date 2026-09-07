"""Shared fixtures for DeFi Yield Aggregator direct-mode tests."""

import json
import os
import pytest

CONTRACT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "defi_yield_aggregator.py",
)

CHAIN = "Ethereum"
PROTOCOL = "Aave"
ASSET = "USDC"
APY_URL = "https://defillama.com/yields/aave-usdc"
TVL_URL = "https://defillama.com/protocol/aave"

POOL_DATA_LOW = json.dumps({
    "apy": "4.5%",
    "tvl": "12000000000",
    "risk_level": "LOW",
    "risk_score": 90,
    "summary": "Aave USDC is a mature, high-TVL pool with stable returns.",
})

POOL_DATA_MEDIUM = json.dumps({
    "apy": "12.0%",
    "tvl": "500000000",
    "risk_level": "MEDIUM",
    "risk_score": 65,
    "summary": "Higher APY comes with moderate smart contract and liquidity risk.",
})

POOL_DATA_HIGH = json.dumps({
    "apy": "45.0%",
    "tvl": "2000000",
    "risk_level": "HIGH",
    "risk_score": 25,
    "summary": "Very high APY from a new protocol with low TVL.",
})

POOL_DATA_MALFORMED = json.dumps({
    "apy": "abc",
    "tvl": "xyz",
    "risk_level": "extreme",
    "risk_score": -500,
    "summary": "Malformed to test normalization.",
})

LLM_PATTERN = r".*DeFi yield aggregator.*"

APY_PATTERN = r".*defillama.*yields.*"
TVL_PATTERN = r".*defillama.*protocol.*"
APY_BODY = "Aave V3 USDC pool: APY 4.5%, TVL $12B"
TVL_BODY = "Aave total value locked: $12.1B across all chains"


def with_pool_data(vm, apy_body=APY_BODY, tvl_body=TVL_BODY):
    vm.mock_web(APY_PATTERN, {"method": "GET", "status": 200, "body": apy_body})
    vm.mock_web(TVL_PATTERN, {"method": "GET", "status": 200, "body": tvl_body})


@pytest.fixture
def aggregator(direct_vm, direct_deploy):
    vm = direct_vm
    vm.mock_llm(LLM_PATTERN, POOL_DATA_LOW)
    with_pool_data(vm)
    c = direct_deploy(CONTRACT)
    return vm, c

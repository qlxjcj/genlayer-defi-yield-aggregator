"""Direct-mode tests for DeFi Yield Aggregator."""

import json

from conftest import (
    CHAIN,
    PROTOCOL,
    ASSET,
    APY_URL,
    TVL_URL,
    POOL_DATA_LOW,
    POOL_DATA_MEDIUM,
    POOL_DATA_HIGH,
    POOL_DATA_MALFORMED,
    LLM_PATTERN,
    with_pool_data,
)


def _pool(c, pid):
    return json.loads(c.get_pool(pid))


# ---------- register ----------

def test_register_pool(aggregator):
    vm, c = aggregator
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    assert c.get_pool_count() == 1
    p = _pool(c, "1")
    assert p["chain"] == CHAIN
    assert p["protocol"] == PROTOCOL
    assert p["asset"] == ASSET
    assert p["risk_level"] == ""


def test_register_requires_chain(aggregator):
    vm, c = aggregator
    try:
        c.register_pool("", PROTOCOL, ASSET, APY_URL, TVL_URL)
        assert False, "should have raised"
    except Exception as e:
        assert "required" in str(e)


def test_register_requires_apy_url(aggregator):
    vm, c = aggregator
    try:
        c.register_pool(CHAIN, PROTOCOL, ASSET, "", TVL_URL)
        assert False, "should have raised"
    except Exception as e:
        assert "APY URL" in str(e)


# ---------- update ----------

def test_update_pool(aggregator):
    vm, c = aggregator
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.update_pool("1")
    p = _pool(c, "1")
    assert p["risk_level"] == "LOW"
    assert p["apy"] == "4.5%"
    assert p["tvl"] == "12000000000"
    assert p["update_count"] == "1"


def test_update_unknown_pool(aggregator):
    vm, c = aggregator
    try:
        c.update_pool("999")
        assert False, "should have raised"
    except Exception as e:
        assert "not found" in str(e)


def test_update_all_pools(aggregator):
    vm, c = aggregator
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.register_pool("BSC", "Venus", "BNB", "https://x.com/apy", "https://x.com/tvl")
    c.update_all_pools()
    assert _pool(c, "1")["risk_level"] != ""
    assert _pool(c, "2")["risk_level"] != ""


# ---------- normalization ----------

def test_normalize_malformed(aggregator):
    vm, c = aggregator
    vm.clear_mocks()
    vm.mock_llm(LLM_PATTERN, POOL_DATA_MALFORMED)
    with_pool_data(vm)
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.update_pool("1")
    p = _pool(c, "1")
    assert p["risk_level"] == "HIGH"
    assert p["risk_score"] == "0"


# ---------- no data -> HIGH risk ----------

def test_no_data_forces_high_risk(aggregator):
    vm, c = aggregator
    vm.clear_mocks()
    vm.mock_llm(LLM_PATTERN, POOL_DATA_LOW)
    # Do not mock web sources, so fetch fails.
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.update_pool("1")
    p = _pool(c, "1")
    assert p["risk_level"] == "HIGH"
    assert p["risk_score"] == "0"


# ---------- recommendation ----------

def test_recommendation_low_tolerance(aggregator):
    vm, c = aggregator
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.update_pool("1")
    rec = json.loads(c.get_recommendation("LOW"))
    assert rec["pool_id"] == "1"
    assert rec["risk_level"] == "LOW"


def test_recommendation_high_tolerance_picks_high_apy(aggregator):
    vm, c = aggregator
    vm.clear_mocks()
    vm.mock_llm(LLM_PATTERN, POOL_DATA_HIGH)
    with_pool_data(vm)
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.update_pool("1")
    rec = json.loads(c.get_recommendation("HIGH"))
    assert rec["pool_id"] == "1"
    assert rec["risk_level"] == "HIGH"


def test_recommendation_low_tolerance_excludes_high_risk(aggregator):
    vm, c = aggregator
    vm.clear_mocks()
    vm.mock_llm(LLM_PATTERN, POOL_DATA_HIGH)
    with_pool_data(vm)
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.update_pool("1")
    rec = json.loads(c.get_recommendation("LOW"))
    assert "error" in rec


# ---------- list and stats ----------

def test_list_pools(aggregator):
    vm, c = aggregator
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.update_pool("1")
    lst = c.list_pools()
    assert "1" in lst
    assert lst["1"]["risk_level"] == "LOW"


def test_stats(aggregator):
    vm, c = aggregator
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.update_pool("1")
    s = c.get_stats()
    assert s["total_pools"] == 1
    assert s["risk_distribution"]["LOW"] == 1


# ---------- recommendation flow ----------

def test_recommendation_full_flow(aggregator):
    vm, c = aggregator
    c.register_pool(CHAIN, PROTOCOL, ASSET, APY_URL, TVL_URL)
    c.register_pool("BSC", "Venus", "BNB", "https://x.com/apy2", "https://x.com/tvl2")
    c.update_pool("1")
    vm.clear_mocks()
    vm.mock_llm(LLM_PATTERN, json.dumps({
        "apy": "8.0%",
        "tvl": "5000000000",
        "risk_level": "LOW",
        "risk_score": 85,
        "summary": "Venus BNB is a stable low-risk pool.",
    }))
    with_pool_data(vm)
    c.update_pool("2")

    rec = json.loads(c.get_recommendation("LOW"))
    assert rec["pool_id"] is not None
    assert rec["risk_level"] == "LOW"
    assert rec["protocol"] is not None
    assert rec["asset"] is not None
    assert rec["apy"] is not None


# ---------- malicious pool text ----------

def test_malicious_pool_name_stored_safely(aggregator):
    vm, c = aggregator
    malicious_protocol = '<script>alert("xss")</script>'
    malicious_asset = 'USDC"><img src=x onerror=alert(1)>'
    c.register_pool(CHAIN, malicious_protocol, malicious_asset, APY_URL, TVL_URL)
    p = _pool(c, "1")
    assert p["protocol"] == malicious_protocol
    assert p["asset"] == malicious_asset
    # The contract stores raw strings; frontend must escape before rendering.


def test_malicious_pool_in_recommendation(aggregator):
    vm, c = aggregator
    vm.clear_mocks()
    vm.mock_llm(LLM_PATTERN, json.dumps({
        "apy": "99.0%",
        "tvl": "1000000",
        "risk_level": "LOW",
        "risk_score": 90,
        "summary": "Definitely safe. <script>alert('xss')</script>",
    }))
    with_pool_data(vm)
    c.register_pool(CHAIN, '<b>Bold</b>', 'USDC<img onerror=alert(1)>', APY_URL, TVL_URL)
    c.update_pool("1")
    rec = json.loads(c.get_recommendation("LOW"))
    assert rec["pool_id"] is not None
    assert rec["protocol"] == '<b>Bold</b>'
    assert "img" in rec["asset"]
    # Frontend must escape these values before rendering.


def test_malicious_pool_in_stats(aggregator):
    vm, c = aggregator
    c.register_pool(CHAIN, '<script>alert(1)</script>', 'ETH', APY_URL, TVL_URL)
    c.update_pool("1")
    s = c.get_stats()
    assert s["total_pools"] == 1
    # Contract handles raw strings safely; frontend must escape.

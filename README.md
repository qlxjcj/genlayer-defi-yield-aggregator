# DeFi Yield Aggregator — GenLayer

A GenLayer intelligent contract that aggregates DeFi yield pool data across
multiple chains, assesses risk via AI consensus, and recommends the best pool
for a user's risk tolerance.

## Lifecycle

```
register_pool(chain, protocol, asset, apy_url, tvl_url)   # register a yield pool
update_pool(pool_id)                                        # fetch real APY/TVL + AI risk assessment
update_all_pools()                                          # update every registered pool
get_recommendation(risk_tolerance)                          # get best pool for LOW/MEDIUM/HIGH risk
list_pools()                                                # view all pools with latest data
get_stats()                                                 # pool count and risk distribution
```

## How consensus is used

Each `update_pool` runs inside a `gl.eq_principle.prompt_comparative` block:

1. `gl.nondet.web.render` fetches live APY and TVL data from real sources
   (inside the consensus flow, not before it).
2. `gl.nondet.exec_prompt` asks the model to assess the pool's risk.
3. `gl.eq_principle.prompt_comparative` requires validators to agree on:
   - **risk_level** (LOW / MEDIUM / HIGH) — exact match
   - **risk_score** (0..100) — within 10 points
   - **apy_retrieved** and **tvl_retrieved** — exact, so validators agree on
     which data sources were actually fetched

## Risk assessment

Risk is assessed based on protocol maturity, TVL size, and APY sustainability:

| Level | Risk Score | Description |
|-------|------------|-------------|
| LOW   | 70-100     | Mature protocol, high TVL, stable APY |
| MEDIUM| 40-69      | Moderate risk, lower TVL or newer protocol |
| HIGH  | 0-39       | New protocol, very low TVL, or unsustainable APY |

## Explicit risk-downgrade

If neither APY nor TVL data can be retrieved, the pool is forced to HIGH risk
with score 0 — the contract never guesses favorable conditions without data.

## Recommendation engine

`get_recommendation(risk_tolerance)` filters pools by the user's risk tolerance
and returns the one with the highest APY within the allowed risk level:

- **LOW tolerance** → only LOW-risk pools
- **MEDIUM tolerance** → LOW and MEDIUM pools
- **HIGH tolerance** → all pools

## Contract functions

### Write
- `register_pool(chain, protocol, asset, apy_url, tvl_url)` — register a yield pool
- `update_pool(pool_id)` — fetch real data, assess risk, store result
- `update_all_pools()` — update every registered pool

### View
- `get_pool(pool_id)` — pool details
- `list_pools()` — all pools with latest data
- `get_recommendation(risk_tolerance)` — best pool for risk level
- `get_pool_count()` — number of pools
- `get_stats()` — pool count and risk distribution

## Testing

```bash
python -m pytest tests/direct/ -v
```

## License

MIT

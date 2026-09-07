# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
import json
from dataclasses import dataclass
from genlayer import *


@allow_storage
@dataclass
class Pool:
    pool_id: str
    chain: str
    protocol: str
    asset: str
    apy_url: str
    tvl_url: str
    apy: str
    tvl: str
    risk_level: str
    risk_score: str
    last_updated: str
    update_count: str


class DeFiYieldAggregator(gl.Contract):
    pools: TreeMap[str, str]
    pool_count: u256
    update_seq: u256

    RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")

    def __init__(self):
        self.pool_count = 0
        self.update_seq = 0

    def _now(self) -> int:
        return 1000000 + int(self.update_seq)

    def _decode_body(self, content) -> str:
        body = getattr(content, "body", None)
        if body is None:
            return str(content)
        if isinstance(body, bytes):
            return body.decode("utf-8", errors="replace")
        return str(body)

    def _fetch_pool_data(self, chain: str, protocol: str, asset: str, apy_url: str, tvl_url: str) -> dict:
        def fetch_and_assess() -> dict:
            apy_body = ""
            apy_retrieved = False
            try:
                content = gl.nondet.web.render(apy_url)
                apy_body = self._decode_body(content)[:1500]
                apy_retrieved = True
            except Exception:
                pass

            tvl_body = ""
            tvl_retrieved = False
            try:
                content = gl.nondet.web.render(tvl_url)
                tvl_body = self._decode_body(content)[:1500]
                tvl_retrieved = True
            except Exception:
                pass

            task = f"""
You are a DeFi yield aggregator. Analyze this yield pool and assess its risk.

Pool: {protocol} - {asset} on {chain}

APY Source ({"retrieved" if apy_retrieved else "NOT RETRIEVED"}):
{apy_body or "[no data]"}

TVL Source ({"retrieved" if tvl_retrieved else "NOT RETRIEVED"}):
{tvl_body or "[no data]"}

If neither source was retrieved, you MUST return risk_level HIGH, risk_score 0,
apy "0", and tvl "0".

Assess:
1. Current APY (extract from data, estimate if not explicit)
2. TVL (extract from data)
3. Risk level (LOW/MEDIUM/HIGH) based on protocol maturity, TVL size, APY sustainability
4. Risk score (0-100, higher = safer)

Respond ONLY in this JSON format:
{{
    "apy": str,
    "tvl": str,
    "risk_level": "LOW" | "MEDIUM" | "HIGH",
    "risk_score": int,
    "summary": str
}}
"""
            result = gl.nondet.exec_prompt(task)
            if isinstance(result, str):
                result = json.loads(result.replace("```json", "").replace("```", ""))
            if not isinstance(result, dict):
                raise gl.vm.UserError("[LLM_ERROR] LLM returned non-dict result")
            result["apy_retrieved"] = apy_retrieved
            result["tvl_retrieved"] = tvl_retrieved
            return result

        principle = (
            "Two results are equivalent if risk_level (LOW/MEDIUM/HIGH) matches exactly, "
            "risk_score differs by at most 10 points, apy_retrieved matches exactly, and "
            "tvl_retrieved matches exactly. Minor differences in APY/TVL numbers and summary "
            "wording are acceptable."
        )
        return gl.eq_principle.prompt_comparative(fetch_and_assess, principle)

    def _normalize_result(self, v: dict) -> dict:
        risk_level = str(v.get("risk_level", "")).upper()
        if risk_level not in self.RISK_LEVELS:
            risk_level = "HIGH"
        try:
            risk_score = int(v.get("risk_score", 0))
        except Exception:
            risk_score = 0
        if risk_score < 0:
            risk_score = 0
        if risk_score > 100:
            risk_score = 100

        apy_retrieved = bool(v.get("apy_retrieved", False))
        tvl_retrieved = bool(v.get("tvl_retrieved", False))

        if not apy_retrieved and not tvl_retrieved:
            risk_level = "HIGH"
            risk_score = 0

        return {
            "apy": str(v.get("apy", "0")),
            "tvl": str(v.get("tvl", "0")),
            "risk_level": risk_level,
            "risk_score": risk_score,
            "apy_retrieved": apy_retrieved,
            "tvl_retrieved": tvl_retrieved,
            "summary": str(v.get("summary", "")),
        }

    @gl.public.write
    def register_pool(self, chain: str, protocol: str, asset: str, apy_url: str, tvl_url: str):
        if not chain or not protocol or not asset:
            raise gl.vm.UserError("Chain, protocol, and asset are required")
        apy_url = (apy_url or "").strip()
        tvl_url = (tvl_url or "").strip()
        if not apy_url or not apy_url.startswith("http"):
            raise gl.vm.UserError("A valid APY URL is required")
        if not tvl_url or not tvl_url.startswith("http"):
            raise gl.vm.UserError("A valid TVL URL is required")

        self.pool_count += 1
        pool_id = str(self.pool_count)

        pool = Pool(
            pool_id=pool_id,
            chain=chain.strip(),
            protocol=protocol.strip(),
            asset=asset.strip(),
            apy_url=apy_url,
            tvl_url=tvl_url,
            apy="0",
            tvl="0",
            risk_level="",
            risk_score="",
            last_updated="0",
            update_count="0",
        )
        self.pools[pool_id] = json.dumps(pool.__dict__)
        idx = json.loads(self.pools.get("__index", "[]"))
        idx.append(pool_id)
        self.pools["__index"] = json.dumps(idx)

    @gl.public.write
    def update_pool(self, pool_id: str):
        pool_id = str(pool_id)
        pool = json.loads(self.pools.get(pool_id, "{}"))
        if not pool:
            raise gl.vm.UserError("Pool not found")

        result = self._normalize_result(
            self._fetch_pool_data(pool["chain"], pool["protocol"], pool["asset"], pool["apy_url"], pool["tvl_url"])
        )

        self.update_seq += 1
        pool["apy"] = result["apy"]
        pool["tvl"] = result["tvl"]
        pool["risk_level"] = result["risk_level"]
        pool["risk_score"] = str(result["risk_score"])
        pool["last_updated"] = str(self._now())
        pool["update_count"] = str(int(pool["update_count"]) + 1)
        self.pools[pool_id] = json.dumps(pool)

    @gl.public.write
    def update_all_pools(self):
        pool_ids = json.loads(self.pools.get("__index", "[]"))
        for pool_id in pool_ids:
            try:
                self.update_pool(pool_id)
            except Exception:
                pass

    @gl.public.view
    def get_pool(self, pool_id: str) -> str:
        return self.pools.get(str(pool_id), "{}")

    @gl.public.view
    def get_pool_count(self) -> int:
        return self.pool_count

    @gl.public.view
    def list_pools(self) -> dict:
        result = {}
        for k, v in self.pools.items():
            if k == "__index":
                continue
            pool = json.loads(v)
            result[k] = {
                "chain": pool["chain"],
                "protocol": pool["protocol"],
                "asset": pool["asset"],
                "apy": pool["apy"],
                "tvl": pool["tvl"],
                "risk_level": pool["risk_level"],
                "risk_score": pool["risk_score"],
                "last_updated": pool["last_updated"],
            }
        return result

    @gl.public.view
    def get_recommendation(self, risk_tolerance: str) -> str:
        risk_tolerance = risk_tolerance.upper()
        if risk_tolerance not in self.RISK_LEVELS:
            return json.dumps({"error": "Risk tolerance must be LOW, MEDIUM, or HIGH"})

        best_pool = None
        best_apy = -1.0

        for k, v in self.pools.items():
            if k == "__index":
                continue
            pool = json.loads(v)
            if not pool["apy"] or pool["apy"] == "0":
                continue
            if pool["risk_level"] not in self.RISK_LEVELS:
                continue

            risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
            pool_risk = risk_order.get(pool["risk_level"], 2)
            tolerance = risk_order.get(risk_tolerance, 2)
            if pool_risk > tolerance:
                continue

            try:
                apy = float(pool["apy"].replace("%", ""))
            except Exception:
                continue

            if apy > best_apy:
                best_apy = apy
                best_pool = pool

        if best_pool:
            return json.dumps({
                "pool_id": best_pool["pool_id"],
                "chain": best_pool["chain"],
                "protocol": best_pool["protocol"],
                "asset": best_pool["asset"],
                "apy": best_pool["apy"],
                "tvl": best_pool["tvl"],
                "risk_level": best_pool["risk_level"],
                "risk_score": best_pool["risk_score"],
            })
        return json.dumps({"error": "No suitable pool found"})

    @gl.public.view
    def get_stats(self) -> dict:
        total = 0
        risk_dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for k, v in self.pools.items():
            if k == "__index":
                continue
            total += 1
            pool = json.loads(v)
            if pool["risk_level"] in risk_dist:
                risk_dist[pool["risk_level"]] += 1
        return {
            "total_pools": total,
            "risk_distribution": risk_dist,
        }

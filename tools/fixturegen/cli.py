"""CLI for Fixture Generator: generate test dataset for pipelines & 10M benchmark (DE-0.3)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Any

from dotenv import load_dotenv

from tools.fixturegen.generator import FixtureConfig, generate_fixtures

load_dotenv()


async def insert_batches(
    uri: str,
    db_name: str,
    cfg: FixtureConfig,
    batch_size: int = 5000,
) -> None:
    from reflex_mongo.client import get_db, make_client
    from reflex_mongo.collections import ATTEMPTS_TS, PROBES_TS, REQUESTS_TS

    client = make_client(uri, app_name="reflex-fixturegen")
    db = get_db(client, db_name)

    print(f"Generating {cfg.total_requests:,} requests with seed={cfg.seed}...")
    t0 = time.time()

    req_batch: list[dict[str, Any]] = []
    att_batch: list[dict[str, Any]] = []
    probe_batch: list[dict[str, Any]] = []

    inserted_reqs = 0
    inserted_atts = 0

    for req, atts, probe in generate_fixtures(cfg):
        req_batch.append(req)
        att_batch.extend(atts)
        if probe:
            probe_batch.append(probe)

        if len(req_batch) >= batch_size:
            await db[REQUESTS_TS].insert_many(req_batch, ordered=False)
            await db[ATTEMPTS_TS].insert_many(att_batch, ordered=False)
            if probe_batch:
                await db[PROBES_TS].insert_many(probe_batch, ordered=False)

            inserted_reqs += len(req_batch)
            inserted_atts += len(att_batch)
            req_batch.clear()
            att_batch.clear()
            probe_batch.clear()

            elapsed = time.time() - t0
            rate = inserted_reqs / max(0.001, elapsed)
            print(f"  Inserted {inserted_reqs:,} reqs ({inserted_atts:,} atts) | {rate:.0f} req/s")

    if req_batch:
        await db[REQUESTS_TS].insert_many(req_batch, ordered=False)
        await db[ATTEMPTS_TS].insert_many(att_batch, ordered=False)
        if probe_batch:
            await db[PROBES_TS].insert_many(probe_batch, ordered=False)
        inserted_reqs += len(req_batch)
        inserted_atts += len(att_batch)

    await client.close()
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.2f}s. Total: {inserted_reqs:,} requests, {inserted_atts:,} attempts.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic attempts/requests/probes fixtures"
    )
    parser.add_argument("--count", type=int, default=1000, help="Number of requests to generate")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument("--rps", type=float, default=20.0, help="Simulated request rate")
    parser.add_argument("--batch-size", type=int, default=2000, help="Batch size for insert")
    parser.add_argument("--db", type=str, default="reflex", help="Mongo database name")
    parser.add_argument(
        "--mongo-uri", type=str, default="", help="Mongo URI (defaults to MONGODB_URI in env)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Count documents without inserting")

    args = parser.parse_args()
    cfg = FixtureConfig(total_requests=args.count, seed=args.seed, rps=args.rps)

    if args.dry_run:
        t0 = time.time()
        reqs = 0
        atts = 0
        probes = 0
        for _, a, p in generate_fixtures(cfg):
            reqs += 1
            atts += len(a)
            if p:
                probes += 1
        elapsed = time.time() - t0
        print(
            f"Dry run generated {reqs:,} requests, {atts:,} attempts, {probes:,} probes in {elapsed:.3f}s ({reqs / elapsed:.0f} req/s)"
        )
        return

    uri = args.mongo_uri or os.environ.get("MONGODB_URI", "")
    if not uri:
        print("Error: MONGODB_URI is not set and --mongo-uri not specified.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(insert_batches(uri, args.db, cfg, batch_size=args.batch_size))


if __name__ == "__main__":
    main()

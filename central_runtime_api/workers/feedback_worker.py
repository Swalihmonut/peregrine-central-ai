"""Background Continuous Improvement Worker for Central Arabic AI API."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

from central_runtime_api.config import get_default_config
from central_runtime_api.services.feedback_store import FeedbackStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] FeedbackWorker: %(message)s",
)
logger = logging.getLogger("FeedbackWorker")


class ContinuousLearningWorker:
    """Processes learning feedback into versioned candidate datasets with strict consent and PII safeguards."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.store = FeedbackStore(self.data_dir)
        self.version_registry = self.data_dir / "dataset_versions.json"

    def process_cycle(self, target_version: str = "v0.1.0-candidates") -> int:
        """Run single batch candidate aggregation cycle."""
        logger.info("Executing continuous learning cycle for target version: %s", target_version)
        count, path = self.store.generate_candidate_dataset(target_version)
        logger.info("Candidate dataset generation complete. Added %d records to %s", count, path)
        self._update_version_registry(target_version, count, str(path))
        return count

    def _update_version_registry(self, version: str, record_count: int, file_path: str):
        """Update dataset version catalog with audit trail."""
        registry: Dict[str, Any] = {}
        if self.version_registry.exists():
            try:
                with open(self.version_registry, "r", encoding="utf-8") as f:
                    registry = json.load(f)
            except Exception:
                registry = {}

        registry[version] = {
            "record_count": record_count,
            "file_path": file_path,
            "status": "pending_philologist_review",
            "model_update_eligible": False,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "safety_rules": {
                "auto_train_disabled": True,
                "live_weight_updates_blocked": True,
                "human_eval_required_before_promotion": True,
            },
        }

        with open(self.version_registry, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Central AI Continuous Learning Worker")
    parser.add_argument("--version", type=str, default="v0.1.0-candidates", help="Target dataset candidate version")
    parser.add_argument("--interval", type=int, default=0, help="Run interval in seconds (0 for one-off batch)")
    args = parser.parse_args()

    config = get_default_config()
    worker = ContinuousLearningWorker(config.data_dir)

    if args.interval == 0:
        count = worker.process_cycle(args.version)
        print(f"One-off learning cycle finished. Processed {count} candidate records.")
        return 0

    print(f"Starting feedback worker daemon (Interval: {args.interval}s, Version: {args.version})...")
    try:
        while True:
            worker.process_cycle(args.version)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Worker stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

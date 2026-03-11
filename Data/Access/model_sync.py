# model_sync.py: Upload/download RL model files to/from Supabase Storage.
# Part of LeoBook Data — Access Layer
#
# Classes: ModelSync
# Usage:
#   ModelSync.push()  → uploads Data/Store/models/ → Supabase "models" bucket
#   ModelSync.pull()  → downloads Supabase "models" bucket → Data/Store/models/

import os
import logging
from pathlib import Path
from typing import Optional, List

from Data.Access.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# Files to sync (relative to models dir)
MODEL_FILES = [
    "leobook_base.pth",
    "adapter_registry.json",
    "training_config.json",
    "phase1_latest.pth",
    "phase2_latest.pth",
    "phase3_latest.pth",
]

# Also sync checkpoint directory
CHECKPOINT_GLOB = "checkpoints/*.pth"

BUCKET_NAME = "models"
PROJECT_ROOT = Path(__file__).parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "Data" / "Store" / "models"


class ModelSync:
    """Upload and download RL model files to/from Supabase Storage."""

    def __init__(self):
        self.supabase = get_supabase_client()
        if not self.supabase:
            raise RuntimeError("Supabase client not available. Check SUPABASE_URL and SUPABASE_KEY in .env")
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Create the models bucket if it doesn't exist."""
        try:
            buckets = self.supabase.storage.list_buckets()
            exists = any(b.name == BUCKET_NAME for b in buckets)
            if not exists:
                print(f"  [ModelSync] Creating storage bucket: '{BUCKET_NAME}'")
                self.supabase.storage.create_bucket(BUCKET_NAME, options={"public": False})
                print(f"  [ModelSync] ✓ Bucket created")
        except Exception as e:
            logger.warning(f"  [ModelSync] Bucket check/create warning: {e}")
            # May fail if bucket already exists or permissions differ — continue anyway

    def _list_local_files(self) -> List[Path]:
        """Find all model files that exist locally."""
        files = []
        for name in MODEL_FILES:
            p = MODELS_DIR / name
            if p.exists():
                files.append(p)

        # Add checkpoint files
        ckpt_dir = MODELS_DIR / "checkpoints"
        if ckpt_dir.exists():
            for p in sorted(ckpt_dir.glob("*.pth")):
                files.append(p)

        return files

    def push(self):
        """Upload all local model files to Supabase Storage."""
        files = self._list_local_files()
        if not files:
            print("  [ModelSync] No model files found in Data/Store/models/. Nothing to push.")
            return

        print(f"\n  [ModelSync] PUSH: {len(files)} file(s) → Supabase Storage (bucket: '{BUCKET_NAME}')")
        uploaded = 0

        for local_path in files:
            remote_path = str(local_path.relative_to(MODELS_DIR)).replace("\\", "/")
            size_mb = local_path.stat().st_size / (1024 * 1024)

            try:
                with open(local_path, "rb") as f:
                    file_content = f.read()

                self.supabase.storage.from_(BUCKET_NAME).upload(
                    path=remote_path,
                    file=file_content,
                    file_options={"x-upsert": "true", "content-type": "application/octet-stream"},
                )
                uploaded += 1
                print(f"    ✓ {remote_path} ({size_mb:.1f} MB)")
            except Exception as e:
                print(f"    ✗ {remote_path}: {e}")

        print(f"\n  [ModelSync] Push complete: {uploaded}/{len(files)} files uploaded.")

    def pull(self):
        """Download all model files from Supabase Storage."""
        print(f"\n  [ModelSync] PULL: Supabase Storage (bucket: '{BUCKET_NAME}') → Data/Store/models/")

        # List remote files
        remote_files = self._list_remote_files()
        if not remote_files:
            print("  [ModelSync] No files found in remote bucket. Nothing to pull.")
            return

        os.makedirs(MODELS_DIR, exist_ok=True)
        os.makedirs(MODELS_DIR / "checkpoints", exist_ok=True)
        downloaded = 0

        for remote_path in remote_files:
            local_path = MODELS_DIR / remote_path.replace("/", os.sep)
            os.makedirs(local_path.parent, exist_ok=True)

            try:
                res = self.supabase.storage.from_(BUCKET_NAME).download(remote_path)
                with open(local_path, "wb") as f:
                    f.write(res)
                size_mb = local_path.stat().st_size / (1024 * 1024)
                downloaded += 1
                print(f"    ✓ {remote_path} ({size_mb:.1f} MB)")
            except Exception as e:
                print(f"    ✗ {remote_path}: {e}")

        print(f"\n  [ModelSync] Pull complete: {downloaded}/{len(remote_files)} files downloaded.")

    def _list_remote_files(self, prefix: str = "") -> List[str]:
        """Recursively list all files in the remote bucket."""
        files = []
        try:
            items = self.supabase.storage.from_(BUCKET_NAME).list(prefix)
            for item in items:
                name = item.get("name", "")
                # If it has no metadata.size, it's a folder
                if item.get("metadata") is None or item.get("id") is None:
                    # It's a folder — recurse
                    sub_prefix = f"{prefix}/{name}" if prefix else name
                    files.extend(self._list_remote_files(sub_prefix))
                else:
                    full_path = f"{prefix}/{name}" if prefix else name
                    files.append(full_path)
        except Exception as e:
            logger.error(f"  [ModelSync] Failed to list remote files: {e}")
        return files

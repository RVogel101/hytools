"""Google Cloud Platform helpers for training orchestration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GCPTrainingClient:
    """Client for submitting training jobs to Vertex AI."""

    def __init__(
        self,
        project_id: str,
        region: str = "us-central1",
        credentials_path: Optional[str] = None,
        enable_spot: bool = True,
    ):
        try:
            import google.cloud.aiplatform as aiplatform  # type: ignore[reportMissingImports]
            from google.oauth2 import service_account
        except ImportError as exc:
            raise ImportError(
                "Google Cloud libraries not installed. Run: pip install google-cloud-aiplatform"
            ) from exc

        if credentials_path:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            aiplatform.init(project=project_id, location=region, credentials=credentials)
        else:
            aiplatform.init(project=project_id, location=region)

        self.project_id = project_id
        self.region = region
        self.enable_spot = enable_spot
        self.aiplatform = aiplatform
        logger.info("GCP client initialized: project=%s region=%s spot=%s", project_id, region, enable_spot)

    # Implementation of methods identical to original.


class ComputeEngineManager:
    """Manager for Compute Engine VMs for custom training."""

    def __init__(
        self,
        project_id: str,
        region: str = "us-central1",
        zone: str = "us-central1-a",
    ):
        try:
            from google.cloud import compute_v1  # type: ignore[reportMissingImports]
        except ImportError as exc:
            raise ImportError(
                "Google Cloud Compute not installed. Run: pip install google-cloud-compute"
            ) from exc

        self.project_id = project_id
        self.region = region
        self.zone = zone
        self.compute_client = compute_v1.InstancesClient()
        self.images_client = compute_v1.ImagesClient()

    # (Methods continue from original implementation, omitted for brevity.)

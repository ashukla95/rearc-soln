from datetime import datetime
from google.cloud import storage
from typing import Any
from urllib.parse import urlencode
import requests
import yaml


class DataUsaIngest:

    def __init__(
        self,
        region: str,
        storage_bkt: str,
        base_url: str,
        resource_path: str,
        query_params: dict[Any, Any]  # maybe pydantic helps!
    ):
        if (
            'drilldowns' in query_params 
            and isinstance(query_params['drilldowns'], list)
        ):
            query_params['drilldowns'] = ','.join(query_params['drilldowns'])
        self.api_url = f"{base_url}/{resource_path}?{urlencode(query_params)}"
        self.region = region
        gcs_client = storage.Client()
        self.__bucket = gcs_client.bucket(
            storage_bkt
        )

    def ingest(self):
        blob = self.__bucket.blob(
            f"datausa/{self.region}/"
            "cube_acs_yg_total_population_data/"
            f"{datetime.now().date().isoformat()}.json"
        )
        blob.content_type = "application/json"
        with requests.get(
            f"{self.api_url}",
            stream=True
        ) as response:
            with blob.open("wb") as writer:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk: 
                        writer.write(chunk)
        print("File write complete.")

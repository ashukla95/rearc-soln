from bs4 import BeautifulSoup
from datetime import datetime
from google.cloud import (
    bigquery,
    storage
)
from io import BytesIO
import re
import requests
import yaml


class BLSIngest:
    def __init__(
        self,
        base_url: str,
        section: str,
        files_to_skip: list[str],
        bq_project_id: str,
        metadata_tbl: str,
        storage_bkt: str
    ):
        self.base_url = f"{base_url}/{section}"
        self.section = section
        self.files_to_skip = files_to_skip
        self.bq_project_id = bq_project_id
        self.metadata_tbl = metadata_tbl
        self.storage_bkt = storage_bkt
    
    def __get_file_tags(self):
        response = requests.get(
            self.base_url,
            headers={
                "User-Agent": "Chrome/120.0.0.0 Safari/537.36"  # noqa
            }
        ).text
        soup = BeautifulSoup(response)
        a_tags = soup.find('pre').find_all('a')
        file_tags = [
            tag for tag in a_tags if tag.text not in self.files_to_skip
        ]
        return file_tags
    
    def __parse_file_tags(self, file_tags):
        parsed_file_details = []
        for file_tag in file_tags:
            prev_sib = file_tag.previous_sibling.strip()
            prev_sib = re.sub(r'\s+', ' ', prev_sib)
            prev_sib = prev_sib.split(" ")
            parsed_file_details.append(
                {
                    "file_name": file_tag.text,
                    "access_url": file_tag.get("href"),
                    "last_update_date": datetime.strptime(
                        f"{prev_sib[0].strip()} {prev_sib[1].strip()} {prev_sib[2].strip()}",  # noqa
                        "%m/%d/%Y %I:%M %p"
                    ).isoformat()
                } 
            )
        return parsed_file_details

    def __get_file_list(self):
        file_tags = self.__get_file_tags()
        parsed_file_details = self.__parse_file_tags(file_tags)
        return parsed_file_details
    
    def __get_metadata(self):
        bq_client = bigquery.Client(
            project=self.bq_project_id
        )

        # only using this as section is input dependent.
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "section", 
                    "STRING", 
                    self.section
                ),
            ]
        )
        query_ = f"""
            select 
                file_name
                ,cast(last_update_ts as string) as last_update_ts
            from `{self.metadata_tbl}`
            where bls_section=@section
        """
        response = bq_client.query(
            query_,
            job_config=job_config
        ).result()
        metadata_dict = {
            row['file_name']: {
                'last_update_ts': row['last_update_ts']
            }
            for row in response
        }
        return metadata_dict


    def __ingest_file(self, file_name: str):
        gcs_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        with requests.get(
            f"{self.base_url}/{file_name}",
            stream=True
        ) as response:

        
    
    def ingest(self):
        print(
            f"Starting ingestion for: {self.section}"
        )
        file_list = self.__get_file_list()
        ingested_file_metadata = self.__get_metadata()
        for file in file_list:
            file_name = file['file_name']
            print(f"Ingesting: {file_name}")
            if (
                file_name not in ingested_file_metadata 
                or datetime.strptime(
                    file['last_update_ts'], 
                    "%Y-%m-%dT%H:%M:%S"
                ) > datetime.strptime(
                    ingested_file_metadata[file_name], 
                    "%Y-%m-%dT%H:%M:%S"
                )
            ):
                self.__ingest_file(file_name)



from module.bls.ingest import BLSIngest
from module.datausa.ingest import DataUsaIngest
from flask import (
    Flask,
    make_response
)
import logging
import yaml


app = Flask(__name__)
app_config = None
with open("config.yaml", "r") as fp:
    app_config = yaml.safe_load(fp)


@app.route("/ingest/bls/timeseries/<string:section>", methods=["GET"])
def ingest_bls_data(section):
    try:
        bls_config = app_config["bls"]
        if section not in bls_config["timeseries"]:
            return make_response(
                "Please enter valid section value.",
                400
            )
        bls_ingestor = BLSIngest(
            base_url=bls_config["timeseries"]["base_url"],
            section=section,
            files_to_skip=bls_config["timeseries"][section]["files_to_skip"],
            metadata_tbl=(
                f"{bls_config['metadata']['bq_dataset']}."
                f"{bls_config['metadata']['bq_table']}"
            ),
            bq_project_id=bls_config['metadata']['bq_project'],
            storage_bkt=bls_config["timeseries"]['storage_bkt']
        )
        bls_ingestor.ingest()
    except Exception as exc:
        return make_response("Error! Please investigate", 500)    
    return make_response("Ingestion Complete", 200)


@app.route("/ingest/datausa/<string:region_name>", methods=["GET"])
def ingest_honolulu_datasusa(region_name):
    try:
        region_name = region_name.lower()
        datausa_config = app_config["api"]["datausa"]
        if region_name not in datausa_config:
            return make_response(
                "Please enter valid region name.",
                400
            )
        DataUsaIngest(
            region=region_name,
            storage_bkt=datausa_config["storage_bkt"],
            base_url=datausa_config[region_name]["base_url"],
            resource_path=datausa_config[region_name]["resource_path"],
            query_params=datausa_config[region_name]["query_params"]
        ).ingest()
    except Exception as exc:
        return make_response("Error! Please investigate", 500)
    return make_response("Ingestion Complete", 200)


if __name__ == "__main__":
    app.run(
        "127.0.0.1",
        port=8080,
        debug=True  # leaving this as true given that it's a take home.
    )

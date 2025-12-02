
from module.bls.ingest import BLSIngest

from flask import Flask

import logging
import yaml


app = Flask(__name__)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
app_config = None
with open("config.yaml", "r") as fp:
    app_config = yaml.safe_load(fp)


@app.route("/ingest/bls/timeseries/<string:section>", methods=["GET"])
def ingest_bls_data(section):
    bls_config = app_config["bls"]
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
    return "200"


if __name__ == "__main__":
    app.run(
        "127.0.0.1",
        port=8080,
        debug=True
    )
    

    


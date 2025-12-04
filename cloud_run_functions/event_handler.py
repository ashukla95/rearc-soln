from datetime import datetime
from flask import Flask, request
from cloudevents.http import from_http
import functions_framework
from google.cloud import storage
from io import StringIO
import json
import pandas as pd
import yaml


app = Flask(__name__)


def calc_part_1(df):
    filtered_df = df.query('2013 <= year <= 2018')
    mean_population = filtered_df['population'].mean()
    std_population = filtered_df['population'].std()
    print(f"""
        part 1:
        mean: {mean_population}
        standard deviation: {std_population}
    """)


def calc_part_2(part_1_df):
    yearly_sum = part_1_df.groupby(['series_id', 'year'])['value'].sum().reset_index()
    yearly_sum = yearly_sum.rename(columns={'value': 'val_sum'})
    # print(yearly_sum)
    idx_max_value = yearly_sum.groupby('series_id')['val_sum'].idxmax()
    # print(f"id max: {idx_max_value}")
    best_year_report = yearly_sum.loc[idx_max_value].rename(columns={'val_sum': 'value'})
    final_report = best_year_report[['series_id', 'year', 'value']].reset_index().drop("index", axis=1)
    print(f"""
        part 2:
        {final_report}
    """)


def calc_part_3(part_1_df, part_2_df):
    for col in ['series_id', 'period']:
        part_1_df[col] = part_1_df[col].str.strip()
    df_ts_filtered = part_1_df[
        (part_1_df['series_id'] == 'PRS30006032') & 
        (part_1_df['period'] == 'Q01')
    ]
    df_pop_filtered = part_2_df[['year', 'population']]
    report_df = df_ts_filtered.merge(
        df_pop_filtered,
        on='year',
        how='left'
    )
    report_df = report_df[['series_id', 'year', 'period', 'value', 'population']]

    print(f"""
        part 3:
        {report_df}
    """)


def read_from_gcs(gcs_bkt, file_name):
    gcs_client = storage.Client()
    bucket = gcs_client.bucket(
        gcs_bkt
    )
    blob = bucket.blob(file_name)
    return blob.download_as_text()
    

def read_bls_file(gcs_bkt, file_name, col_list, sep):  
    data_stream = read_from_gcs(
        gcs_bkt, file_name
    )
    data_stream = StringIO(data_stream)
    df = pd.read_csv(data_stream, sep=sep)
    df.columns = col_list
    return df


def read_datausa_file(gcs_bkt, file_name, col_list):
    data_stream = read_from_gcs(
        gcs_bkt, file_name
    )
    data = json.loads(data_stream)
    df = pd.DataFrame(data["data"])
    df.columns = col_list
    return df


@app.route("/", methods=["POST"])
def event_trigger():
# def event_trigger(cloud_event):
    event = from_http(request.headers, request.get_data())
    print(f"event: {event}")
    file_name = event["data"]["name"]
    if f"cube_acs_yg_total_population_data/{datetime.now().date().isoformat()}.json" not in file_name:  # noqa
        raise Exception("The file uploaded cannot be processed.") 

    app_config = None
    with open("config.yaml", "r") as fp:
        app_config = yaml.safe_load(fp)
    app_config = app_config["event"]
    part_1_df = read_bls_file(
        app_config["storage_bkt"],
        "bls/pub/time.series/pr/pr.data.0.Current",
        app_config["bls"]["metadata"]["pr"]["pr.data.0.Current"]["columns"],
        app_config["bls"]["metadata"]["pr"]["pr.data.0.Current"]["sep"]
    )
    part_2_df = read_datausa_file(
        app_config["storage_bkt"],
        f"datausa/honolulu/cube_acs_yg_total_population_data/{datetime.now().date().isoformat()}.json",
        app_config["datausa"]["honululu"]["columns"]
    )
    calc_part_1(part_2_df)
    calc_part_2(part_1_df)
    calc_part_3(part_1_df, part_2_df)
    return "200"


if __name__ == "__main__":
    app.run(
        "127.0.0.1",
        port=8080,
        debug=True  # leaving this as true given that it's a take home.
    )

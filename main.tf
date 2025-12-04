locals {
  project_id = "turnkey-clover-480017-b8"
  region     = "us-central1"
  gcs_region = "us"
  source_hash = sha1(join("", [for f in fileset("${path.module}/cloud_run_functions", "**"): filesha1("${path.module}/cloud_run_functions/${f}")]))
  image_url  = "gcr.io/${local.project_id}/rearc/ingestion-soln:${local.source_hash}"
  bucket_name = "rearc-soln" 
}

provider "google" {
  project = local.project_id
  region  = local.region
}

# --- 1. Enable Required APIs ---
# Ensures the project has the necessary capabilities enabled
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "cloudbuild.googleapis.com",
    "containerregistry.googleapis.com",
    "cloudscheduler.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

resource "null_resource" "docker_build" {
  triggers = {
    # Re-build if any file in the python folder changes
    dir_sha1 = sha1(join("", [for f in fileset("${path.module}/cloud_run_functions", "**"): filesha1("${path.module}/cloud_run_functions/${f}")]))
  }

  provisioner "local-exec" {
    # Builds the image and pushes it to GCR
    command = "gcloud builds submit --tag ${local.image_url} ${path.module}/cloud_run_functions/"
  }
  
  depends_on = [google_project_service.apis]
}

# --- 2. The Bucket (with Import Logic) ---
import {
  id = local.bucket_name
  to = google_storage_bucket.data_bucket
}

resource "google_storage_bucket" "data_bucket" {
  name                        = local.bucket_name
  location                    = local.gcs_region
  force_destroy               = true
  uniform_bucket_level_access = true
  
  # Ensure APIs are enabled before touching storage
  depends_on = [google_project_service.apis]
}

# --- 3. Service Account for Eventarc ---
resource "google_service_account" "eventarc_invoker" {
  account_id   = "eventarc-gcs-invoker"
  display_name = "Eventarc GCS Trigger Account"
}

# --- 4. HTTP Public Handler Service ---
resource "google_cloud_run_v2_service" "http_api_service" {
  name     = "http-public-handler"
  location = local.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Explicitly allow public internet traffic

  template {
    containers {
      image = local.image_url
      command = ["gunicorn"]
      args    = ["--bind", "0.0.0.0:8080", "http_handler:app"]
    }
  }
  depends_on = [google_project_service.apis]
}

resource "time_sleep" "wait_for_apis" {
  create_duration = "180s"
  
  depends_on = [google_project_service.apis, null_resource.docker_build]
}

resource "google_cloud_run_v2_service_iam_member" "http_public_access" {
  location = google_cloud_run_v2_service.http_api_service.location
  name     = google_cloud_run_v2_service.http_api_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- 5. GCS Worker Service (Internal) ---
resource "google_cloud_run_v2_service" "gcs_worker_service" {
  name     = "gcs-event-handler"
  location = local.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Blocks public internet, allows Eventarc

  template {
    containers {
      image = local.image_url
      command = ["gunicorn"]
      args    = ["--bind", "0.0.0.0:8080", "event_handler:app"]
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "eventarc_invoker_permission" {
  location = google_cloud_run_v2_service.gcs_worker_service.location
  name     = google_cloud_run_v2_service.gcs_worker_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.eventarc_invoker.email}"
}

resource "google_project_iam_member" "eventarc_receiver_binding" {
  project = local.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.eventarc_invoker.email}"
}

data "google_storage_project_service_account" "gcs_account" {
}

# 2. Grant GCS permission to publish to Pub/Sub (Required for Eventarc)
resource "google_project_iam_member" "gcs_pubsub_publishing" {
  project = local.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

# --- 6. The Eventarc Trigger ---
resource "google_eventarc_trigger" "gcs_trigger" {
  name     = "gcs-finalized-trigger"
  location = local.gcs_region

  service_account = google_service_account.eventarc_invoker.email

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  
  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.data_bucket.name
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.gcs_worker_service.name
      region  = local.region
    }
  }
  
  depends_on = [google_storage_bucket.data_bucket]
}

# --- Outputs ---
output "http_service_url" {
  description = "Public URL for the HTTP Handler"
  value       = google_cloud_run_v2_service.http_api_service.uri
}

output "gcs_bucket_name" {
  description = "Bucket being watched"
  value       = google_storage_bucket.data_bucket.name
}

resource "google_service_account" "scheduler_sa" {
  account_id   = "scheduler-invoker"
  display_name = "Cloud Scheduler Invoker Account"
}

resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker_permission" {
  location = google_cloud_run_v2_service.http_api_service.location
  name     = google_cloud_run_v2_service.http_api_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}


resource "google_cloud_scheduler_job" "bls_trigger" {
  name             = "bls-daily-trigger"
  description      = "Triggers the endpoint to ingest BLS-PR data"
  schedule         = "0 18 * * *"
  time_zone        = "America/New_York"
  attempt_deadline = "538s"
  region           = local.region  

  http_target {
    http_method = "GET"
    
    # 👇 CHANGE THIS PATH to your specific endpoint
    uri = "${google_cloud_run_v2_service.http_api_service.uri}/ingest/bls/timeseries/pr"

    # Authenticate as the service account
    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }

  depends_on = [google_project_service.apis]
}


resource "google_cloud_scheduler_job" "datausa_trigger" {
  name             = "datausa-honolulu-daily-trigger"
  description      = "Triggers the endpoint to ingest honolulu's data via datausa"
  schedule         = "0 19 * * *"
  time_zone        = "America/New_York"
  attempt_deadline = "538s"
  region           = local.region  

  http_target {
    http_method = "GET"
    
    # 👇 CHANGE THIS PATH to your specific endpoint
    uri = "${google_cloud_run_v2_service.http_api_service.uri}/ingest/datausa/honolulu"

    # Authenticate as the service account
    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }

  depends_on = [google_project_service.apis]
}
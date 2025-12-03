locals {
  project_id = "turnkey-clover-480017-b8"
  region     = "us-central1"
  gcs_region = "us"
  image_url  = "gcr.io/${local.project_id}/rearc/ingestion-soln:latest"
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
    "storage.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
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
  ingress  = "INGRESS_TRAFFIC_ALL" # Explicitly allow public internet traffic

  template {
    containers {
      image = local.image_url
      command = ["gunicorn"]
      args    = ["--bind", "0.0.0.0:8080", "http_handler:app"]
    }
  }
  depends_on = [google_project_service.apis]
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
  ingress  = "INGRESS_INTERNAL_ONLY" # Blocks public internet, allows Eventarc

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

# --- 6. The Eventarc Trigger ---
resource "google_eventarc_trigger" "gcs_trigger" {
  name     = "gcs-finalized-trigger"
  location = local.region

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
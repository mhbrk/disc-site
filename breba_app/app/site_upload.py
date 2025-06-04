from google.cloud import storage
import os

def upload_site(local_path: str, site_name: str, bucket_name: str = "breba-sites"):
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    print(f"Current working directory: {os.getcwd()}")

    for root, _, files in os.walk(local_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, local_path)
            blob_path = f"sites/{site_name}/{rel_path}"

            blob = bucket.blob(blob_path)
            blob.upload_from_filename(file_path)
            blob.make_public()  # Optional: make each file public

            print(f"Uploaded: {blob_path}")

    blob = bucket.blob(f"sites/{site_name}/index.html")
    url = f"https://storage.googleapis.com/{bucket.name}/{blob.name}"
    return url

# Example usage
upload_site("/Users/yason/breba/disc-site/sites/test-site", "test-site")
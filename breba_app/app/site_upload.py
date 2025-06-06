from google.cloud import storage
import os

def upload_site(local_path: str, site_name: str, bucket_name: str = "breba-sites"):
    """
    Uploads site to google cloud
    Example: upload_site("/Users/yason/breba/disc-site/sites/test-site", "test-site")
    :param local_path: relative or absolute path of local directory
    :param site_name: site name where all the files will be stored
    :param bucket_name: name of the bucket
    :return:
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    print(f"Current working directory: {os.getcwd()}")

    for root, _, files in os.walk(local_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, local_path)
            blob_path = f"{site_name}/{rel_path}"

            blob = bucket.blob(blob_path)
            blob.upload_from_filename(file_path)
            blob.make_public()  # Optional: make each file public

            print(f"Uploaded: {blob_path}")

    blob = bucket.blob(f"{site_name}/index.html")
    url = f"https://storage.googleapis.com/{bucket.name}/{blob.name}"
    return url


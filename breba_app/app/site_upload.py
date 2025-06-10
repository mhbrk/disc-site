from google.cloud import storage

from common.storage import copy_directory


def upload_site(session_id: str, site_name: str, bucket_name: str = "breba-sites"):
    """
    Uploads site to google cloud
    Example: upload_site("/Users/yason/breba/disc-site/sites/test-site", "test-site")
    :param session_id: session id used for locating site files
    :param site_name: site name where all the files will be stored
    :param bucket_name: name of the bucket
    :return:
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    copy_directory(
        source_bucket_name="breba-private",
        target_bucket_name=bucket_name, prefix=session_id, target_prefix=site_name
    )

    blob = bucket.blob(f"{site_name}/index.html")
    url = f"https://storage.googleapis.com/{bucket.name}/{blob.name}"
    return url

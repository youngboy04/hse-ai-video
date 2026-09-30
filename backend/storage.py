"""Local media store, optionally mirrored to an S3-compatible private bucket."""

import os
from pathlib import Path

ROOT = Path(os.getenv("MEDIA_DIR", "./data/snapshots"))


def save_media(key, data, content_type):
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / key).write_bytes(data)
    # Keep local evidence as the durable write path; the outbox mirror retries S3.


def get_path(key):
    path = ROOT / key
    if path.is_file():
        return path
    if os.getenv("S3_ENDPOINT"):
        client = s3_client()
        ROOT.mkdir(parents=True, exist_ok=True)
        client.download_file(os.getenv("S3_BUCKET", "hse-evidence"), key, str(path))
        return path
    return None


def s3_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name="us-east-1",
        config=Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 1}),
    )


def mirror(key, content_type):
    from botocore.exceptions import ClientError

    client = s3_client()
    bucket = os.getenv("S3_BUCKET", "hse-evidence")
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as exc:
        if str(exc.response["Error"]["Code"]) not in ("404", "NoSuchBucket"):
            raise
        client.create_bucket(Bucket=bucket)
    client.upload_file(
        str(ROOT / key), bucket, key, ExtraArgs={"ContentType": content_type}
    )

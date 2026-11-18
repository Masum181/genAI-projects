from io import BytesIO

from minio import Minio

from app.config import settings


client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False
)


def create_bucket():
    bucket = settings.minio_bucket

    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_to_minio(
    file_content: bytes,
    object_name: str
):
    client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=object_name,
        data=BytesIO(file_content),
        length=len(file_content),
        content_type="text/x-python"
    )

    return object_name
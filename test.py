# from minio import Minio

# client = Minio(
#     "localhost:9000",
#     access_key="minioadmin",
#     secret_key="change-this-to-a-long-password",
#     secure=False,
#     region="us-east-1",
# )

# print(client.list_buckets())

from minio import Minio

client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="change-this-to-a-long-password",
    secure=False,
    region="us-east-1",
)

bucket = "enterprise-rag-documents"

if not client.bucket_exists(bucket):
    client.make_bucket(
        bucket,
        location="us-east-1"
    )
    print("Bucket created successfully!")
else:
    print("Bucket already exists!")
import boto3
from django.conf import settings
import os
import uuid


def upload_to_s3(file_obj, filename, folder="whatsapp_media"):
    """
    Uploads a file object to S3 and returns the public URL.
    """
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )

    # Generate unique filename to avoid collisions
    unique_filename = f"{uuid.uuid4()}_{filename}"
    s3_path = f"{folder}/{unique_filename}"

    try:
        s3_client.upload_fileobj(
            file_obj,
            settings.AWS_STORAGE_BUCKET_NAME,
            s3_path,
            ExtraArgs={
                "ACL": "public-read"
            },  # Assuming public read is required for WhatsApp
        )

        # Construct the URL
        url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{s3_path}"
        return url
    except Exception as e:
        print(f"S3 Upload failed: {str(e)}")
        return None


def upload_local_file_to_s3(local_path, folder="whatsapp_media"):
    """
    Uploads a local file to S3 and returns the public URL.
    """
    filename = os.path.basename(local_path)
    with open(local_path, "rb") as f:
        return upload_to_s3(f, filename, folder)

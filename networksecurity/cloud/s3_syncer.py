import os
import boto3

class S3Sync:
    def sync_folder_to_s3(self, folder, aws_bucket_url):
        # 1. Setup the client to talk to Cloudflare R2
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL")
        )

        # 2. Get the bucket name and folder path from the URL
        bucket_name = aws_bucket_url.split("/")[2]
        prefix = "/".join(aws_bucket_url.split("/")[3:])

        # 3. Walk through the local folder and upload every file
        for root, dirs, files in os.walk(folder):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, folder)
                
                # --- THE FIX IS HERE ---
                # 1. Join the prefix and relative path
                # 2. Force replace all backslashes (\) with forward slashes (/)
                s3_path = os.path.join(prefix, relative_path).replace("\\", "/")
                
                print(f"Uploading {local_path} to {s3_path}")
                s3_client.upload_file(local_path, bucket_name, s3_path)

    def sync_folder_from_s3(self, folder, aws_bucket_url):
        # The download logic usually works fine because os.path.join 
        # on Windows naturally creates the backslashes your local OS needs.
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL")
        )

        bucket_name = aws_bucket_url.split("/")[2]
        prefix = "/".join(aws_bucket_url.split("/")[3:])

        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        
        if 'Contents' in response:
            for obj in response['Contents']:
                file_key = obj['Key']
                if file_key.endswith('/'): continue
                
                relative_key = os.path.relpath(file_key, prefix)
                local_file_path = os.path.join(folder, relative_key)
                
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                
                print(f"Downloading {file_key} to {local_file_path}")
                s3_client.download_file(bucket_name, file_key, local_file_path)
                
             
import os
import io
from datetime import datetime
from typing import Optional, Dict, Any
from minio import Minio
from minio.error import S3Error


class MinIOService:
    """
    A robust MinIO service for saving and retrieving data with folder organization.
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = True,
        region: Optional[str] = None,
    ):
        """
        Initialize MinIO service with connection parameters.

        Args:
            endpoint: MinIO server endpoint (e.g., 'localhost:9000')
            access_key: Access key for authentication
            secret_key: Secret key for authentication
            bucket_name: Default bucket name to use
            secure: Whether to use HTTPS (default: True)
            region: Optional region name
        """
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.secure = secure
        self.region = region

        # Initialize MinIO client
        self.client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
            region=self.region,
        )

        # Ensure bucket exists
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """
        Ensure the bucket exists, create if it doesn't.
        """
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name, location=self.region)
                print(f"Created bucket: {self.bucket_name}")
        except S3Error as e:
            raise Exception(f"Failed to create/verify bucket {self.bucket_name}: {e}")

    def save(
        self,
        data: bytes,
        filename: str,
        content_type: str,
        bucket_name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Save data to MinIO with folder organization.

        Args:
            data: Binary data to save
            filename: File name (e.g., 'AAPL_1min.csv')
            bucket_name: Optional bucket name override
            metadata: Optional metadata dictionary

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            bucket = bucket_name or self.bucket_name

            # Convert bytes to BytesIO stream
            data_stream = io.BytesIO(data)

            # Upload the data
            self.client.put_object(
                bucket_name=bucket,
                object_name=filename,
                data=data_stream,
                length=len(data),
                content_type=content_type,
                metadata=metadata,
            )

            print(f"Successfully saved {filename} to bucket {bucket}")
            return True

        except S3Error as e:
            print(f"Failed to save {filename}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error saving {filename}: {e}")
            return False

    def save_file(
        self,
        file_path: str,
        folder: str,
        filename: Optional[str] = None,
        bucket_name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Save a local file to MinIO.

        Args:
            file_path: Path to local file
            folder: Destination folder path
            filename: Optional custom filename (uses original if None)
            bucket_name: Optional bucket name override
            metadata: Optional metadata dictionary

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return False

            # Use original filename if not provided
            if filename is None:
                filename = os.path.basename(file_path)

            bucket = bucket_name or self.bucket_name
            object_name = f"{folder.strip('/')}/{filename}"

            # Upload the file
            self.client.fput_object(
                bucket_name=bucket,
                object_name=object_name,
                file_path=file_path,
                metadata=metadata,
            )

            print(f"Successfully uploaded {file_path} as {object_name}")
            return True

        except S3Error as e:
            print(f"Failed to upload {file_path}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error uploading {file_path}: {e}")
            return False

    def retrieve(
        self, folder: str, filename: str, bucket_name: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Retrieve data from MinIO.

        Args:
            folder: Folder path
            filename: File name
            bucket_name: Optional bucket name override

        Returns:
            bytes: File data if successful, None otherwise
        """
        try:
            bucket = bucket_name or self.bucket_name
            object_name = f"{folder.strip('/')}/{filename}"

            response = self.client.get_object(bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()

            return data

        except S3Error as e:
            print(f"Failed to retrieve {folder}/{filename}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error retrieving {folder}/{filename}: {e}")
            return None

    def retrieve_to_file(
        self,
        folder: str,
        filename: str,
        local_path: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """
        Retrieve data from MinIO and save to local file.

        Args:
            folder: Folder path in MinIO
            filename: File name in MinIO
            local_path: Local file path to save to
            bucket_name: Optional bucket name override

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            bucket = bucket_name or self.bucket_name
            object_name = f"{folder.strip('/')}/{filename}"

            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            self.client.fget_object(bucket, object_name, local_path)

            print(f"Successfully downloaded {object_name} to {local_path}")
            return True

        except S3Error as e:
            print(f"Failed to download {folder}/{filename}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error downloading {folder}/{filename}: {e}")
            return False

    def save_data_with_date(
        self,
        data: bytes,
        date: datetime,
        category: str,
        filename: str,
        bucket_name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Save data organized by date and category.

        Args:
            data: Binary data to save
            date: Date for folder organization
            category: Category subfolder (e.g., 'stocks', 'crypto')
            filename: File name
            bucket_name: Optional bucket name override
            metadata: Optional metadata dictionary

        Returns:
            bool: True if successful, False otherwise
        """
        folder = f"{category}/{date.strftime('%Y-%m-%d')}"
        return self.save(data, folder, filename, bucket_name, metadata)

    def retrieve_data_with_date(
        self,
        date: datetime,
        category: str,
        filename: str,
        bucket_name: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Retrieve data organized by date and category.

        Args:
            date: Date for folder lookup
            category: Category subfolder
            filename: File name
            bucket_name: Optional bucket name override

        Returns:
            bytes: File data if successful, None otherwise
        """
        folder = f"{category}/{date.strftime('%Y-%m-%d')}"
        return self.retrieve(folder, filename, bucket_name)

    def list_objects(
        self,
        folder: str = "",
        bucket_name: Optional[str] = None,
        recursive: bool = False,
    ) -> list:
        """
        List objects in a folder.

        Args:
            folder: Folder path (empty for root)
            bucket_name: Optional bucket name override
            recursive: Whether to list recursively

        Returns:
            list: List of object names
        """
        try:
            bucket = bucket_name or self.bucket_name
            prefix = folder.strip("/") + "/" if folder else ""

            objects = self.client.list_objects(
                bucket, prefix=prefix, recursive=recursive
            )

            return [obj.object_name for obj in objects]

        except S3Error as e:
            print(f"Failed to list objects in {folder}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error listing objects in {folder}: {e}")
            return []

    def delete_object(
        self, folder: str, filename: str, bucket_name: Optional[str] = None
    ) -> bool:
        """
        Delete an object from MinIO.

        Args:
            folder: Folder path
            filename: File name
            bucket_name: Optional bucket name override

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            bucket = bucket_name or self.bucket_name
            object_name = f"{folder.strip('/')}/{filename}"

            self.client.remove_object(bucket, object_name)

            print(f"Successfully deleted {object_name}")
            return True

        except S3Error as e:
            print(f"Failed to delete {folder}/{filename}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error deleting {folder}/{filename}: {e}")
            return False

    def object_exists(
        self, folder: str, filename: str, bucket_name: Optional[str] = None
    ) -> bool:
        """
        Check if an object exists in MinIO.

        Args:
            folder: Folder path
            filename: File name
            bucket_name: Optional bucket name override

        Returns:
            bool: True if object exists, False otherwise
        """
        try:
            bucket = bucket_name or self.bucket_name
            object_name = f"{folder.strip('/')}/{filename}"

            self.client.stat_object(bucket, object_name)
            return True

        except S3Error:
            return False
        except Exception:
            return False

    def get_object_info(
        self, folder: str, filename: str, bucket_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get object information including metadata.

        Args:
            folder: Folder path
            filename: File name
            bucket_name: Optional bucket name override

        Returns:
            dict: Object info if successful, None otherwise
        """
        try:
            bucket = bucket_name or self.bucket_name
            object_name = f"{folder.strip('/')}/{filename}"

            stat = self.client.stat_object(bucket, object_name)

            return {
                "object_name": stat.object_name,
                "size": stat.size,
                "etag": stat.etag,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata,
                "content_type": stat.content_type,
            }

        except S3Error as e:
            print(f"Failed to get info for {folder}/{filename}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error getting info for {folder}/{filename}: {e}")
            return None

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, BinaryIO
from app.config import get_settings

settings = get_settings()


class BaseStorageService(ABC):
    @abstractmethod
    def save_file(self, file_obj: BinaryIO, filename: str, folder: str = "uploads") -> str:
        """Saves file and returns storage_key."""
        pass

    @abstractmethod
    def get_file_path_or_url(self, storage_key: str) -> str:
        """Returns accessible path or presigned URL for storage_key."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Deletes file by storage_key."""
        pass


class LocalStorageService(BaseStorageService):
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.uploads_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, file_obj: BinaryIO, filename: str, folder: str = "uploads") -> str:
        target_dir = self.base_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = Path(filename).name
        target_path = target_dir / safe_filename

        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)

        return f"{folder}/{safe_filename}"

    def get_file_path_or_url(self, storage_key: str) -> str:
        return f"/uploads/{storage_key.replace('uploads/', '')}"

    def delete_file(self, storage_key: str) -> bool:
        clean_key = storage_key.replace('uploads/', '')
        file_path = self.base_dir / clean_key
        if file_path.exists():
            file_path.unlink()
            return True
        return False


class S3StorageService(BaseStorageService):
    """S3 / MinIO storage service implementation for cloud or local DPDP on-prem deployments."""
    def __init__(self, bucket_name: str = "sanjeevani-medical"):
        self.bucket_name = bucket_name
        # Placeholder for boto3 / minio client initialization if credentials configured

    def save_file(self, file_obj: BinaryIO, filename: str, folder: str = "uploads") -> str:
        storage_key = f"{folder}/{filename}"
        # In production with boto3: s3_client.upload_fileobj(file_obj, self.bucket_name, storage_key)
        return storage_key

    def get_file_path_or_url(self, storage_key: str) -> str:
        # In production with boto3: return s3_client.generate_presigned_url('get_object', Params={'Bucket': self.bucket_name, 'Key': storage_key}, ExpiresIn=3600)
        return f"https://s3.amazonaws.com/{self.bucket_name}/{storage_key}"

    def delete_file(self, storage_key: str) -> bool:
        return True


def get_storage_service() -> BaseStorageService:
    # Defaults to LocalStorageService for dev/on-prem, easily switched via config
    return LocalStorageService()

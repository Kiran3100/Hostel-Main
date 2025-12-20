"""
File Storage Service

Abstract cloud storage operations with support for multiple providers.
"""

import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional, List, BinaryIO
from datetime import datetime, timedelta
import logging
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.exceptions import StorageException

logger = logging.getLogger(__name__)


class StorageProvider(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    async def upload_file(
        self,
        file_content: bytes,
        storage_key: str,
        content_type: str,
        metadata: Dict[str, Any],
        is_public: bool = False,
    ) -> Dict[str, Any]:
        """Upload file to storage."""
        pass

    @abstractmethod
    async def download_file(self, storage_key: str) -> bytes:
        """Download file from storage."""
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """Delete file from storage."""
        pass

    @abstractmethod
    async def generate_download_url(
        self,
        storage_key: str,
        expires_in: int,
        filename: Optional[str] = None,
    ) -> str:
        """Generate pre-signed download URL."""
        pass

    @abstractmethod
    async def initiate_multipart_upload(
        self,
        storage_key: str,
        content_type: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Initiate multipart upload."""
        pass

    @abstractmethod
    async def get_multipart_upload_url(
        self,
        storage_key: str,
        upload_id: str,
        part_number: int,
    ) -> str:
        """Get pre-signed URL for multipart part upload."""
        pass

    @abstractmethod
    async def complete_multipart_upload(
        self,
        storage_key: str,
        upload_id: str,
        parts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Complete multipart upload."""
        pass


class S3StorageProvider(StorageProvider):
    """AWS S3 storage provider implementation."""

    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.bucket_name = settings.S3_BUCKET_NAME
        self.cdn_domain = settings.CDN_DOMAIN

    async def upload_file(
        self,
        file_content: bytes,
        storage_key: str,
        content_type: str,
        metadata: Dict[str, Any],
        is_public: bool = False,
    ) -> Dict[str, Any]:
        """Upload file to S3."""
        try:
            extra_args = {
                'ContentType': content_type,
                'Metadata': {k: str(v) for k, v in metadata.items()},
            }

            if is_public:
                extra_args['ACL'] = 'public-read'

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=storage_key,
                Body=file_content,
                **extra_args,
            )

            # Get object info
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )

            url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{storage_key}"
            
            public_url = None
            if is_public and self.cdn_domain:
                public_url = f"https://{self.cdn_domain}/{storage_key}"

            return {
                "storage_key": storage_key,
                "url": url,
                "public_url": public_url,
                "etag": response['ETag'].strip('"'),
                "size_bytes": response['ContentLength'],
            }

        except ClientError as e:
            logger.error(f"S3 upload failed: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to upload file to S3: {str(e)}")

    async def download_file(self, storage_key: str) -> bytes:
        """Download file from S3."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )
            return response['Body'].read()

        except ClientError as e:
            logger.error(f"S3 download failed: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to download file from S3: {str(e)}")

    async def delete_file(self, storage_key: str) -> bool:
        """Delete file from S3."""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )
            return True

        except ClientError as e:
            logger.error(f"S3 delete failed: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to delete file from S3: {str(e)}")

    async def generate_download_url(
        self,
        storage_key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
    ) -> str:
        """Generate pre-signed download URL."""
        try:
            params = {
                'Bucket': self.bucket_name,
                'Key': storage_key,
            }

            if filename:
                params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'

            url = self.s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params=params,
                ExpiresIn=expires_in,
            )

            return url

        except ClientError as e:
            logger.error(f"Failed to generate download URL: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to generate download URL: {str(e)}")

    async def initiate_multipart_upload(
        self,
        storage_key: str,
        content_type: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Initiate multipart upload."""
        try:
            response = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=storage_key,
                ContentType=content_type,
                Metadata={k: str(v) for k, v in metadata.items()},
            )

            return {
                "upload_id": response['UploadId'],
                "storage_key": storage_key,
            }

        except ClientError as e:
            logger.error(f"Failed to initiate multipart upload: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to initiate multipart upload: {str(e)}")

    async def get_multipart_upload_url(
        self,
        storage_key: str,
        upload_id: str,
        part_number: int,
    ) -> str:
        """Get pre-signed URL for multipart part upload."""
        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod='upload_part',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': storage_key,
                    'UploadId': upload_id,
                    'PartNumber': part_number,
                },
                ExpiresIn=3600,  # 1 hour
            )

            return url

        except ClientError as e:
            logger.error(f"Failed to generate part upload URL: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to generate part upload URL: {str(e)}")

    async def complete_multipart_upload(
        self,
        storage_key: str,
        upload_id: str,
        parts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Complete multipart upload."""
        try:
            multipart_upload = {
                'Parts': [
                    {
                        'PartNumber': part['part_number'],
                        'ETag': part['etag'],
                    }
                    for part in sorted(parts, key=lambda x: x['part_number'])
                ]
            }

            response = self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=storage_key,
                UploadId=upload_id,
                MultipartUpload=multipart_upload,
            )

            url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{storage_key}"

            return {
                "storage_key": storage_key,
                "url": url,
                "etag": response['ETag'].strip('"'),
            }

        except ClientError as e:
            logger.error(f"Failed to complete multipart upload: {str(e)}", exc_info=True)
            raise StorageException(f"Failed to complete multipart upload: {str(e)}")


class FileStorageService:
    """
    File storage service with provider abstraction.
    """

    def __init__(self, provider: Optional[StorageProvider] = None):
        """
        Initialize storage service.

        Args:
            provider: Storage provider instance (defaults to S3)
        """
        self.provider = provider or S3StorageProvider()

    async def upload_file(
        self,
        file_content: bytes,
        storage_key: str,
        content_type: str,
        metadata: Dict[str, Any],
        is_public: bool = False,
    ) -> Dict[str, Any]:
        """Upload file to storage."""
        return await self.provider.upload_file(
            file_content=file_content,
            storage_key=storage_key,
            content_type=content_type,
            metadata=metadata,
            is_public=is_public,
        )

    async def download_file(self, storage_key: str) -> bytes:
        """Download file from storage."""
        return await self.provider.download_file(storage_key)

    async def delete_file(self, storage_key: str) -> bool:
        """Delete file from storage."""
        return await self.provider.delete_file(storage_key)

    async def generate_download_url(
        self,
        storage_key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
    ) -> str:
        """Generate pre-signed download URL."""
        return await self.provider.generate_download_url(
            storage_key=storage_key,
            expires_in=expires_in,
            filename=filename,
        )

    async def initiate_multipart_upload(
        self,
        storage_key: str,
        content_type: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Initiate multipart upload."""
        return await self.provider.initiate_multipart_upload(
            storage_key=storage_key,
            content_type=content_type,
            metadata=metadata,
        )

    async def get_multipart_upload_url(
        self,
        storage_key: str,
        upload_id: str,
        part_number: int,
    ) -> str:
        """Get pre-signed URL for multipart part upload."""
        return await self.provider.get_multipart_upload_url(
            storage_key=storage_key,
            upload_id=upload_id,
            part_number=part_number,
        )

    async def complete_multipart_upload(
        self,
        storage_key: str,
        upload_id: str,
        parts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Complete multipart upload."""
        return await self.provider.complete_multipart_upload(
            storage_key=storage_key,
            upload_id=upload_id,
            parts=parts,
        )
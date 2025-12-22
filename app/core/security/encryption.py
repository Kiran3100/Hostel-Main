import base64
import hashlib
import secrets
import os
from typing import Union, Dict, Any, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import json
import logging

logger = logging.getLogger(__name__)

class DataEncryption:
    """Data encryption/decryption utility"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        if encryption_key:
            self.key = encryption_key.encode()
        else:
            self.key = self._derive_key_from_config()
        
        self.fernet = Fernet(base64.urlsafe_b64encode(self.key[:32]))
    
    def encrypt_string(self, plaintext: str) -> str:
        """Encrypt string and return base64 encoded result"""
        try:
            encrypted = self.fernet.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"String encryption failed: {str(e)}")
            raise ValueError("Encryption failed")
    
    def decrypt_string(self, encrypted_data: str) -> str:
        """Decrypt base64 encoded encrypted string"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"String decryption failed: {str(e)}")
            raise ValueError("Decryption failed")
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Encrypt dictionary data"""
        try:
            json_string = json.dumps(data, sort_keys=True)
            return self.encrypt_string(json_string)
        except Exception as e:
            logger.error(f"Dictionary encryption failed: {str(e)}")
            raise ValueError("Dictionary encryption failed")
    
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt dictionary data"""
        try:
            json_string = self.decrypt_string(encrypted_data)
            return json.loads(json_string)
        except Exception as e:
            logger.error(f"Dictionary decryption failed: {str(e)}")
            raise ValueError("Dictionary decryption failed")
    
    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt raw bytes"""
        try:
            return self.fernet.encrypt(data)
        except Exception as e:
            logger.error(f"Bytes encryption failed: {str(e)}")
            raise ValueError("Bytes encryption failed")
    
    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        """Decrypt raw bytes"""
        try:
            return self.fernet.decrypt(encrypted_data)
        except Exception as e:
            logger.error(f"Bytes decryption failed: {str(e)}")
            raise ValueError("Bytes decryption failed")
    
    def _derive_key_from_config(self) -> bytes:
        """Derive encryption key from configuration"""
        # In production, get from secure configuration
        master_key = os.getenv('ENCRYPTION_MASTER_KEY', 'default_master_key_change_in_production')
        salt = os.getenv('ENCRYPTION_SALT', 'default_salt').encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        return kdf.derive(master_key.encode())

class FieldEncryption:
    """Database field encryption utility"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self.data_encryption = DataEncryption(encryption_key)
        # Prefix to identify encrypted fields
        self.encrypted_prefix = "ENC:"
    
    def encrypt_field(self, value: Any) -> str:
        """Encrypt a database field value"""
        if value is None:
            return None
        
        try:
            # Convert to string if not already
            string_value = str(value)
            encrypted = self.data_encryption.encrypt_string(string_value)
            return f"{self.encrypted_prefix}{encrypted}"
        except Exception as e:
            logger.error(f"Field encryption failed: {str(e)}")
            raise ValueError("Field encryption failed")
    
    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a database field value"""
        if not encrypted_value or not encrypted_value.startswith(self.encrypted_prefix):
            # Return as-is if not encrypted
            return encrypted_value
        
        try:
            # Remove prefix and decrypt
            encrypted_data = encrypted_value[len(self.encrypted_prefix):]
            return self.data_encryption.decrypt_string(encrypted_data)
        except Exception as e:
            logger.error(f"Field decryption failed: {str(e)}")
            raise ValueError("Field decryption failed")
    
    def is_encrypted_field(self, value: str) -> bool:
        """Check if field value is encrypted"""
        return bool(value and value.startswith(self.encrypted_prefix))
    
    def encrypt_sensitive_fields(self, data: Dict[str, Any], sensitive_fields: list) -> Dict[str, Any]:
        """Encrypt specified sensitive fields in a dictionary"""
        encrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field] is not None:
                encrypted_data[field] = self.encrypt_field(encrypted_data[field])
        
        return encrypted_data
    
    def decrypt_sensitive_fields(self, data: Dict[str, Any], sensitive_fields: list) -> Dict[str, Any]:
        """Decrypt specified sensitive fields in a dictionary"""
        decrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in decrypted_data and self.is_encrypted_field(str(decrypted_data[field])):
                decrypted_data[field] = self.decrypt_field(decrypted_data[field])
        
        return decrypted_data

class FileEncryption:
    """File encryption/decryption utility"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self.data_encryption = DataEncryption(encryption_key)
        self.chunk_size = 64 * 1024  # 64KB chunks
    
    def encrypt_file(self, input_path: str, output_path: str) -> bool:
        """Encrypt file and save to output path"""
        try:
            with open(input_path, 'rb') as infile, open(output_path, 'wb') as outfile:
                # Read and encrypt file in chunks
                while True:
                    chunk = infile.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    encrypted_chunk = self.data_encryption.encrypt_bytes(chunk)
                    # Write chunk size and encrypted chunk
                    outfile.write(len(encrypted_chunk).to_bytes(4, 'big'))
                    outfile.write(encrypted_chunk)
            
            logger.info(f"File encrypted successfully: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"File encryption failed: {str(e)}")
            return False
    
    def decrypt_file(self, input_path: str, output_path: str) -> bool:
        """Decrypt file and save to output path"""
        try:
            with open(input_path, 'rb') as infile, open(output_path, 'wb') as outfile:
                while True:
                    # Read chunk size
                    size_bytes = infile.read(4)
                    if not size_bytes:
                        break
                    
                    chunk_size = int.from_bytes(size_bytes, 'big')
                    
                    # Read and decrypt chunk
                    encrypted_chunk = infile.read(chunk_size)
                    if not encrypted_chunk:
                        break
                    
                    decrypted_chunk = self.data_encryption.decrypt_bytes(encrypted_chunk)
                    outfile.write(decrypted_chunk)
            
            logger.info(f"File decrypted successfully: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"File decryption failed: {str(e)}")
            return False
    
    def encrypt_file_in_memory(self, file_data: bytes) -> bytes:
        """Encrypt file data in memory"""
        return self.data_encryption.encrypt_bytes(file_data)
    
    def decrypt_file_in_memory(self, encrypted_data: bytes) -> bytes:
        """Decrypt file data in memory"""
        return self.data_encryption.decrypt_bytes(encrypted_data)

class KeyManager:
    """Encryption key management utility"""
    
    def __init__(self):
        self.key_store = {}  # In production, use secure key store
        self.master_key = self._load_master_key()
    
    def generate_key(self, key_id: str, key_type: str = "fernet") -> str:
        """Generate and store encryption key"""
        try:
            if key_type == "fernet":
                key = Fernet.generate_key()
                key_str = key.decode()
            elif key_type == "aes":
                key = secrets.token_bytes(32)
                key_str = base64.urlsafe_b64encode(key).decode()
            else:
                raise ValueError(f"Unsupported key type: {key_type}")
            
            # Encrypt key with master key before storing
            encrypted_key = self._encrypt_key(key_str)
            self.key_store[key_id] = {
                "encrypted_key": encrypted_key,
                "key_type": key_type,
                "created_at": secrets.token_urlsafe(16),
                "status": "active"
            }
            
            logger.info(f"Key generated: {key_id} ({key_type})")
            return key_str
            
        except Exception as e:
            logger.error(f"Key generation failed: {str(e)}")
            raise ValueError("Key generation failed")
    
    def get_key(self, key_id: str) -> Optional[str]:
        """Retrieve and decrypt encryption key"""
        try:
            if key_id not in self.key_store:
                return None
            
            key_data = self.key_store[key_id]
            if key_data["status"] != "active":
                return None
            
            # Decrypt key with master key
            return self._decrypt_key(key_data["encrypted_key"])
            
        except Exception as e:
            logger.error(f"Key retrieval failed: {str(e)}")
            return None
    
    def rotate_key(self, key_id: str) -> str:
        """Rotate encryption key"""
        old_key_data = self.key_store.get(key_id)
        if not old_key_data:
            raise ValueError(f"Key not found: {key_id}")
        
        # Generate new key
        new_key = self.generate_key(f"{key_id}_new", old_key_data["key_type"])
        
        # Mark old key as deprecated
        old_key_data["status"] = "deprecated"
        
        # Replace old key with new one
        self.key_store[key_id] = self.key_store[f"{key_id}_new"]
        del self.key_store[f"{key_id}_new"]
        
        logger.info(f"Key rotated: {key_id}")
        return new_key
    
    def revoke_key(self, key_id: str):
        """Revoke encryption key"""
        if key_id in self.key_store:
            self.key_store[key_id]["status"] = "revoked"
            logger.info(f"Key revoked: {key_id}")
    
    def _load_master_key(self) -> bytes:
        """Load master encryption key"""
        # In production, load from secure hardware or key management service
        master_key_str = os.getenv('MASTER_ENCRYPTION_KEY', 'default_master_key_change_in_production')
        return hashlib.sha256(master_key_str.encode()).digest()
    
    def _encrypt_key(self, key: str) -> str:
        """Encrypt key with master key"""
        fernet = Fernet(base64.urlsafe_b64encode(self.master_key))
        encrypted = fernet.encrypt(key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt key with master key"""
        fernet = Fernet(base64.urlsafe_b64encode(self.master_key))
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()

class TokenEncryption:
    """Token encryption utility"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self.data_encryption = DataEncryption(encryption_key)
    
    def encrypt_token(self, token_data: Dict[str, Any]) -> str:
        """Encrypt token data and return secure token"""
        try:
            # Add timestamp and nonce for security
            token_data.update({
                "iat": secrets.token_urlsafe(16),
                "nonce": secrets.token_hex(16)
            })
            
            return self.data_encryption.encrypt_dict(token_data)
            
        except Exception as e:
            logger.error(f"Token encryption failed: {str(e)}")
            raise ValueError("Token encryption failed")
    
    def decrypt_token(self, encrypted_token: str) -> Dict[str, Any]:
        """Decrypt and validate token"""
        try:
            token_data = self.data_encryption.decrypt_dict(encrypted_token)
            
            # Validate required fields
            if "iat" not in token_data or "nonce" not in token_data:
                raise ValueError("Invalid token structure")
            
            return token_data
            
        except Exception as e:
            logger.error(f"Token decryption failed: {str(e)}")
            raise ValueError("Invalid or corrupted token")
    
    def create_secure_token(self, payload: Dict[str, Any], expires_in: int = 3600) -> str:
        """Create secure encrypted token with expiration"""
        import time
        
        token_data = payload.copy()
        token_data.update({
            "exp": int(time.time()) + expires_in,
            "iat": int(time.time())
        })
        
        return self.encrypt_token(token_data)
    
    def validate_secure_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Validate secure token and check expiration"""
        import time
        
        try:
            token_data = self.decrypt_token(token)
            
            # Check expiration
            if "exp" in token_data and token_data["exp"] < time.time():
                return False, None
            
            return True, token_data
            
        except Exception:
            return False, None

class PIIEncryption:
    """Personally identifiable information encryption"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self.field_encryption = FieldEncryption(encryption_key)
        
        # Define PII field types
        self.pii_fields = {
            'email', 'phone', 'ssn', 'passport', 'license', 'address',
            'first_name', 'last_name', 'date_of_birth', 'bank_account',
            'credit_card', 'tax_id', 'medical_id'
        }
    
    def encrypt_pii_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt all PII fields in data"""
        encrypted_data = data.copy()
        
        for field, value in data.items():
            if self._is_pii_field(field) and value is not None:
                encrypted_data[field] = self.field_encryption.encrypt_field(value)
        
        return encrypted_data
    
    def decrypt_pii_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt all PII fields in data"""
        decrypted_data = data.copy()
        
        for field, value in data.items():
            if self._is_pii_field(field) and self.field_encryption.is_encrypted_field(str(value)):
                decrypted_data[field] = self.field_encryption.decrypt_field(value)
        
        return decrypted_data
    
    def mask_pii_for_logging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask PII fields for safe logging"""
        masked_data = data.copy()
        
        for field, value in data.items():
            if self._is_pii_field(field) and value:
                masked_data[field] = self._mask_value(field, str(value))
        
        return masked_data
    
    def _is_pii_field(self, field_name: str) -> bool:
        """Check if field contains PII"""
        field_lower = field_name.lower()
        return any(pii_type in field_lower for pii_type in self.pii_fields)
    
    def _mask_value(self, field_type: str, value: str) -> str:
        """Mask value based on field type"""
        if 'email' in field_type.lower():
            if '@' in value:
                local, domain = value.split('@', 1)
                return f"{local[0]}***@{domain}"
        
        elif 'phone' in field_type.lower():
            if len(value) >= 4:
                return f"***-***-{value[-4:]}"
        
        elif any(card_type in field_type.lower() for card_type in ['card', 'credit', 'debit']):
            if len(value) >= 4:
                return f"****-****-****-{value[-4:]}"
        
        # Default masking
        if len(value) <= 2:
            return '*' * len(value)
        elif len(value) <= 4:
            return value[0] + '*' * (len(value) - 1)
        else:
            return value[0] + '*' * (len(value) - 2) + value[-1]

class EncryptionKeyRotation:
    """Encryption key rotation manager"""
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self.rotation_schedule = {}
        self.rotation_grace_period = 86400  # 24 hours
    
    def schedule_key_rotation(self, key_id: str, rotation_interval: int):
        """Schedule automatic key rotation"""
        import time
        
        self.rotation_schedule[key_id] = {
            "interval": rotation_interval,
            "last_rotation": time.time(),
            "next_rotation": time.time() + rotation_interval
        }
        
        logger.info(f"Key rotation scheduled: {key_id} (interval: {rotation_interval}s)")
    
    def check_rotation_needed(self, key_id: str) -> bool:
        """Check if key needs rotation"""
        import time
        
        if key_id not in self.rotation_schedule:
            return False
        
        schedule = self.rotation_schedule[key_id]
        return time.time() >= schedule["next_rotation"]
    
    def rotate_key_if_needed(self, key_id: str) -> Optional[str]:
        """Rotate key if rotation is due"""
        if self.check_rotation_needed(key_id):
            return self.rotate_key(key_id)
        return None
    
    def rotate_key(self, key_id: str) -> str:
        """Perform key rotation"""
        import time
        
        new_key = self.key_manager.rotate_key(key_id)
        
        # Update rotation schedule
        if key_id in self.rotation_schedule:
            schedule = self.rotation_schedule[key_id]
            schedule["last_rotation"] = time.time()
            schedule["next_rotation"] = time.time() + schedule["interval"]
        
        logger.info(f"Key rotated: {key_id}")
        return new_key
    
    def get_rotation_status(self, key_id: str) -> Dict[str, Any]:
        """Get key rotation status"""
        import time
        
        if key_id not in self.rotation_schedule:
            return {"scheduled": False}
        
        schedule = self.rotation_schedule[key_id]
        current_time = time.time()
        
        return {
            "scheduled": True,
            "interval": schedule["interval"],
            "last_rotation": schedule["last_rotation"],
            "next_rotation": schedule["next_rotation"],
            "time_until_rotation": max(0, schedule["next_rotation"] - current_time),
            "rotation_overdue": current_time > schedule["next_rotation"]
        }
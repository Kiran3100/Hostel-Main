"""
Encryption and decryption utilities for hostel management system
"""

import os
import base64
from typing import Any, Optional, Union, Dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import json

class EncryptionHelper:
    """Main encryption utility class"""
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        self.key = encryption_key or self._generate_key()
        self.fernet = Fernet(self.key)
        
    @staticmethod
    def _generate_key() -> bytes:
        """Generate encryption key"""
        return Fernet.generate_key()
        
    @staticmethod
    def generate_key_from_password(password: str, salt: bytes = None) -> bytes:
        """Generate encryption key from password"""
        if salt is None:
            salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
        
    def encrypt_string(self, plaintext: str) -> str:
        """Encrypt string data"""
        encrypted_data = self.fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
        
    def decrypt_string(self, encrypted_text: str) -> str:
        """Decrypt string data"""
        encrypted_data = base64.urlsafe_b64decode(encrypted_text.encode())
        decrypted_data = self.fernet.decrypt(encrypted_data)
        return decrypted_data.decode()
        
    def encrypt_json(self, data: Dict[str, Any]) -> str:
        """Encrypt JSON serializable data"""
        json_str = json.dumps(data)
        return self.encrypt_string(json_str)
        
    def decrypt_json(self, encrypted_text: str) -> Dict[str, Any]:
        """Decrypt JSON data"""
        json_str = self.decrypt_string(encrypted_text)
        return json.loads(json_str)
        
    def encrypt_file(self, file_path: str, output_path: str = None) -> str:
        """Encrypt file"""
        with open(file_path, 'rb') as file:
            file_data = file.read()
        encrypted_data = self.fernet.encrypt(file_data)
        
        if output_path is None:
            output_path = f"{file_path}.encrypted"
            
        with open(output_path, 'wb') as output_file:
            output_file.write(encrypted_data)
            
        return output_path
        
    def decrypt_file(self, encrypted_file_path: str, output_path: str = None) -> str:
        """Decrypt file"""
        with open(encrypted_file_path, 'rb') as file:
            encrypted_data = file.read()
        decrypted_data = self.fernet.decrypt(encrypted_data)
        
        if output_path is None:
            output_path = encrypted_file_path.replace('.encrypted', '')
            
        with open(output_path, 'wb') as output_file:
            output_file.write(decrypted_data)
            
        return output_path

class FieldEncryption:
    """Database field encryption utilities"""
    
    def __init__(self, field_keys: Dict[str, bytes] = None):
        self.field_keys = field_keys or {}
        
    def add_field_key(self, field_name: str, key: bytes):
        """Add encryption key for specific field"""
        self.field_keys[field_name] = key
        
    def encrypt_field(self, field_name: str, value: str) -> str:
        """Encrypt specific field value"""
        if field_name not in self.field_keys:
            raise ValueError(f"No encryption key found for field: {field_name}")
            
        fernet = Fernet(self.field_keys[field_name])
        encrypted_data = fernet.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
        
    def decrypt_field(self, field_name: str, encrypted_value: str) -> str:
        """Decrypt specific field value"""
        if field_name not in self.field_keys:
            raise ValueError(f"No encryption key found for field: {field_name}")
            
        fernet = Fernet(self.field_keys[field_name])
        encrypted_data = base64.urlsafe_b64decode(encrypted_value.encode())
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data.decode()

class FileEncryption:
    """File encryption with metadata handling"""
    
    def __init__(self, master_key: bytes = None):
        self.master_key = master_key or Fernet.generate_key()
        
    def encrypt_file_with_metadata(self, file_path: str, metadata: Dict[str, Any] = None) -> Dict[str, str]:
        """Encrypt file with metadata"""
        # Generate unique key for this file
        file_key = Fernet.generate_key()
        fernet = Fernet(file_key)
        
        # Read and encrypt file
        with open(file_path, 'rb') as file:
            file_data = file.read()
        encrypted_file_data = fernet.encrypt(file_data)
        
        # Encrypt the file key with master key
        master_fernet = Fernet(self.master_key)
        encrypted_file_key = master_fernet.encrypt(file_key)
        
        # Create metadata
        file_metadata = {
            'original_filename': os.path.basename(file_path),
            'file_size': len(file_data),
            'encrypted_size': len(encrypted_file_data),
            'encryption_timestamp': int(time.time()),
            'custom_metadata': metadata or {}
        }
        
        encrypted_metadata = master_fernet.encrypt(json.dumps(file_metadata).encode())
        
        return {
            'encrypted_data': base64.urlsafe_b64encode(encrypted_file_data).decode(),
            'encrypted_key': base64.urlsafe_b64encode(encrypted_file_key).decode(),
            'encrypted_metadata': base64.urlsafe_b64encode(encrypted_metadata).decode()
        }
        
    def decrypt_file_with_metadata(self, encrypted_package: Dict[str, str]) -> Dict[str, Any]:
        """Decrypt file with metadata"""
        master_fernet = Fernet(self.master_key)
        
        # Decrypt file key
        encrypted_key = base64.urlsafe_b64decode(encrypted_package['encrypted_key'])
        file_key = master_fernet.decrypt(encrypted_key)
        
        # Decrypt metadata
        encrypted_metadata = base64.urlsafe_b64decode(encrypted_package['encrypted_metadata'])
        metadata_json = master_fernet.decrypt(encrypted_metadata).decode()
        metadata = json.loads(metadata_json)
        
        # Decrypt file data
        fernet = Fernet(file_key)
        encrypted_data = base64.urlsafe_b64decode(encrypted_package['encrypted_data'])
        file_data = fernet.decrypt(encrypted_data)
        
        return {
            'file_data': file_data,
            'metadata': metadata
        }

class PIIEncryption:
    """Personally Identifiable Information encryption"""
    
    PII_FIELDS = [
        'email', 'phone', 'address', 'bank_account', 'tax_id',
        'passport_number', 'driving_license', 'social_security'
    ]
    
    def __init__(self, pii_key: bytes = None):
        self.pii_key = pii_key or Fernet.generate_key()
        self.fernet = Fernet(self.pii_key)
        
    def encrypt_pii_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt PII fields in data dictionary"""
        encrypted_data = data.copy()
        
        for field in self.PII_FIELDS:
            if field in data and data[field]:
                encrypted_value = self.fernet.encrypt(str(data[field]).encode())
                encrypted_data[f"{field}_encrypted"] = base64.urlsafe_b64encode(encrypted_value).decode()
                del encrypted_data[field]
                
        return encrypted_data
        
    def decrypt_pii_data(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt PII fields in data dictionary"""
        decrypted_data = encrypted_data.copy()
        
        for field in self.PII_FIELDS:
            encrypted_field = f"{field}_encrypted"
            if encrypted_field in encrypted_data:
                encrypted_value = base64.urlsafe_b64decode(encrypted_data[encrypted_field])
                decrypted_value = self.fernet.decrypt(encrypted_value).decode()
                decrypted_data[field] = decrypted_value
                del decrypted_data[encrypted_field]
                
        return decrypted_data
        
    def mask_pii_for_display(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask PII data for display purposes"""
        masked_data = data.copy()
        
        masking_rules = {
            'email': lambda x: self._mask_email(x),
            'phone': lambda x: self._mask_phone(x),
            'bank_account': lambda x: self._mask_account_number(x)
        }
        
        for field, masking_func in masking_rules.items():
            if field in data and data[field]:
                masked_data[field] = masking_func(data[field])
                
        return masked_data
        
    @staticmethod
    def _mask_email(email: str) -> str:
        """Mask email address"""
        if '@' not in email:
            return email
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            return email
        return f"{local[:2]}***@{domain}"
        
    @staticmethod
    def _mask_phone(phone: str) -> str:
        """Mask phone number"""
        if len(phone) <= 4:
            return phone
        return f"****{phone[-4:]}"
        
    @staticmethod
    def _mask_account_number(account: str) -> str:
        """Mask account number"""
        if len(account) <= 4:
            return account
        return f"****{account[-4:]}"

class TokenEncryption:
    """Token encryption for secure token storage"""
    
    def __init__(self, token_key: bytes = None):
        self.token_key = token_key or Fernet.generate_key()
        self.fernet = Fernet(self.token_key)
        
    def encrypt_token(self, token_data: Dict[str, Any]) -> str:
        """Encrypt token data"""
        token_json = json.dumps(token_data)
        encrypted_token = self.fernet.encrypt(token_json.encode())
        return base64.urlsafe_b64encode(encrypted_token).decode()
        
    def decrypt_token(self, encrypted_token: str) -> Dict[str, Any]:
        """Decrypt token data"""
        encrypted_data = base64.urlsafe_b64decode(encrypted_token)
        decrypted_data = self.fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())
        
    def create_secure_token(self, payload: Dict[str, Any], 
                           expiry_minutes: int = 60) -> str:
        """Create secure token with expiry"""
        import time
        token_data = {
            'payload': payload,
            'created_at': int(time.time()),
            'expires_at': int(time.time()) + (expiry_minutes * 60)
        }
        return self.encrypt_token(token_data)
        
    def validate_and_extract_token(self, encrypted_token: str) -> Optional[Dict[str, Any]]:
        """Validate token and extract payload"""
        try:
            token_data = self.decrypt_token(encrypted_token)
            import time
            current_time = int(time.time())
            
            if current_time > token_data.get('expires_at', 0):
                return None  # Token expired
                
            return token_data.get('payload')
        except Exception:
            return None

class KeyManager:
    """Encryption key management utilities"""
    
    def __init__(self):
        self.keys: Dict[str, bytes] = {}
        
    def generate_key(self, key_name: str) -> bytes:
        """Generate and store new encryption key"""
        key = Fernet.generate_key()
        self.keys[key_name] = key
        return key
        
    def store_key(self, key_name: str, key: bytes):
        """Store encryption key"""
        self.keys[key_name] = key
        
    def get_key(self, key_name: str) -> Optional[bytes]:
        """Retrieve encryption key"""
        return self.keys.get(key_name)
        
    def rotate_key(self, key_name: str) -> bytes:
        """Rotate encryption key"""
        old_key = self.keys.get(key_name)
        new_key = self.generate_key(key_name)
        
        # Store old key for decryption of existing data
        if old_key:
            self.keys[f"{key_name}_old"] = old_key
            
        return new_key
        
    def export_keys(self, password: str) -> str:
        """Export keys securely"""
        keys_data = {name: base64.urlsafe_b64encode(key).decode() 
                    for name, key in self.keys.items()}
        
        # Encrypt with password
        encryption_key = EncryptionHelper.generate_key_from_password(password)
        fernet = Fernet(encryption_key)
        encrypted_keys = fernet.encrypt(json.dumps(keys_data).encode())
        
        return base64.urlsafe_b64encode(encrypted_keys).decode()
        
    def import_keys(self, encrypted_keys_data: str, password: str):
        """Import keys securely"""
        encryption_key = EncryptionHelper.generate_key_from_password(password)
        fernet = Fernet(encryption_key)
        
        encrypted_data = base64.urlsafe_b64decode(encrypted_keys_data)
        decrypted_data = fernet.decrypt(encrypted_data)
        keys_data = json.loads(decrypted_data.decode())
        
        for name, key_b64 in keys_data.items():
            key = base64.urlsafe_b64decode(key_b64)
            self.keys[name] = key

class EncryptionKeyRotation:
    """Encryption key rotation manager"""
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        
    def rotate_field_encryption_key(self, field_name: str, 
                                   data_updater_callback: callable):
        """Rotate field encryption key and re-encrypt data"""
        old_key = self.key_manager.get_key(field_name)
        new_key = self.key_manager.rotate_key(field_name)
        
        if old_key and data_updater_callback:
            # Callback should handle re-encryption of existing data
            data_updater_callback(old_key, new_key)
            
    def schedule_key_rotation(self, field_name: str, 
                            rotation_interval_days: int = 90):
        """Schedule automatic key rotation"""
        # This would integrate with a task scheduler
        pass
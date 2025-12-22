"""
Hashing utilities for hostel management system
"""

import hashlib
import hmac
import secrets
import bcrypt
from typing import Optional, Dict, Any
import base64
from datetime import datetime, timedelta

class HashingHelper:
    """General purpose hashing utilities"""
    
    @staticmethod
    def md5_hash(data: str) -> str:
        """Generate MD5 hash (for non-security purposes only)"""
        return hashlib.md5(data.encode()).hexdigest()
        
    @staticmethod
    def sha1_hash(data: str) -> str:
        """Generate SHA1 hash"""
        return hashlib.sha1(data.encode()).hexdigest()
        
    @staticmethod
    def sha256_hash(data: str) -> str:
        """Generate SHA256 hash"""
        return hashlib.sha256(data.encode()).hexdigest()
        
    @staticmethod
    def sha512_hash(data: str) -> str:
        """Generate SHA512 hash"""
        return hashlib.sha512(data.encode()).hexdigest()
        
    @staticmethod
    def blake2b_hash(data: str, key: bytes = None) -> str:
        """Generate BLAKE2b hash with optional key"""
        if key:
            return hashlib.blake2b(data.encode(), key=key).hexdigest()
        return hashlib.blake2b(data.encode()).hexdigest()
        
    @staticmethod
    def hash_with_salt(data: str, salt: str = None) -> Dict[str, str]:
        """Generate hash with salt"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        combined = f"{data}{salt}"
        hash_value = hashlib.sha256(combined.encode()).hexdigest()
        
        return {
            'hash': hash_value,
            'salt': salt
        }
        
    @staticmethod
    def verify_hash_with_salt(data: str, stored_hash: str, salt: str) -> bool:
        """Verify hash with salt"""
        combined = f"{data}{salt}"
        calculated_hash = hashlib.sha256(combined.encode()).hexdigest()
        return hmac.compare_digest(calculated_hash, stored_hash)

class PasswordHasher:
    """Secure password hashing utilities"""
    
    DEFAULT_ROUNDS = 12
    
    @classmethod
    def hash_password(cls, password: str, rounds: int = None) -> str:
        """Hash password using bcrypt"""
        if rounds is None:
            rounds = cls.DEFAULT_ROUNDS
            
        salt = bcrypt.gensalt(rounds=rounds)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
        
    @classmethod
    def verify_password(cls, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except ValueError:
            return False
            
    @classmethod
    def needs_rehash(cls, hashed_password: str, rounds: int = None) -> bool:
        """Check if password needs rehashing (for upgraded security)"""
        if rounds is None:
            rounds = cls.DEFAULT_ROUNDS
            
        try:
            # Extract cost from existing hash
            cost = int(hashed_password.split('$')[2])
            return cost < rounds
        except (IndexError, ValueError):
            return True
            
    @classmethod
    def generate_temporary_password(cls, length: int = 12) -> str:
        """Generate temporary password"""
        import string
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))

class TokenHasher:
    """Token hashing for secure token storage"""
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash token for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()
        
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(length)
        
    @staticmethod
    def generate_hex_token(length: int = 32) -> str:
        """Generate hex token"""
        return secrets.token_hex(length)
        
    @staticmethod
    def generate_api_key() -> Dict[str, str]:
        """Generate API key pair"""
        key_id = secrets.token_hex(8)
        secret = secrets.token_urlsafe(48)
        
        return {
            'key_id': key_id,
            'secret': secret,
            'hash': hashlib.sha256(f"{key_id}:{secret}".encode()).hexdigest()
        }
        
    @staticmethod
    def verify_api_key(key_id: str, secret: str, stored_hash: str) -> bool:
        """Verify API key against stored hash"""
        calculated_hash = hashlib.sha256(f"{key_id}:{secret}".encode()).hexdigest()
        return hmac.compare_digest(calculated_hash, stored_hash)

class ChecksumCalculator:
    """File and data integrity checking utilities"""
    
    @staticmethod
    def calculate_file_checksum(file_path: str, algorithm: str = 'sha256') -> str:
        """Calculate file checksum"""
        hash_algorithms = {
            'md5': hashlib.md5(),
            'sha1': hashlib.sha1(),
            'sha256': hashlib.sha256(),
            'sha512': hashlib.sha512()
        }
        
        if algorithm not in hash_algorithms:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
            
        hasher = hash_algorithms[algorithm]
        
        with open(file_path, 'rb') as file:
            for chunk in iter(lambda: file.read(4096), b""):
                hasher.update(chunk)
                
        return hasher.hexdigest()
        
    @staticmethod
    def verify_file_integrity(file_path: str, expected_checksum: str, 
                            algorithm: str = 'sha256') -> bool:
        """Verify file integrity using checksum"""
        calculated_checksum = ChecksumCalculator.calculate_file_checksum(
            file_path, algorithm
        )
        return hmac.compare_digest(calculated_checksum, expected_checksum)
        
    @staticmethod
    def calculate_data_checksum(data: bytes, algorithm: str = 'sha256') -> str:
        """Calculate checksum for byte data"""
        hash_algorithms = {
            'md5': hashlib.md5,
            'sha1': hashlib.sha1,
            'sha256': hashlib.sha256,
            'sha512': hashlib.sha512
        }
        
        if algorithm not in hash_algorithms:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
            
        return hash_algorithms[algorithm](data).hexdigest()

class HMACHelper:
    """HMAC utilities for message authentication"""
    
    @staticmethod
    def generate_hmac(message: str, secret_key: str, algorithm: str = 'sha256') -> str:
        """Generate HMAC for message"""
        algorithms = {
            'sha1': hashlib.sha1,
            'sha256': hashlib.sha256,
            'sha512': hashlib.sha512
        }
        
        if algorithm not in algorithms:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
            
        mac = hmac.new(
            secret_key.encode(),
            message.encode(),
            algorithms[algorithm]
        )
        return mac.hexdigest()
        
    @staticmethod
    def verify_hmac(message: str, secret_key: str, 
                   expected_hmac: str, algorithm: str = 'sha256') -> bool:
        """Verify HMAC"""
        calculated_hmac = HMACHelper.generate_hmac(message, secret_key, algorithm)
        return hmac.compare_digest(calculated_hmac, expected_hmac)
        
    @staticmethod
    def generate_webhook_signature(payload: str, secret: str) -> str:
        """Generate webhook signature"""
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
        
    @staticmethod
    def verify_webhook_signature(payload: str, secret: str, 
                                signature_header: str) -> bool:
        """Verify webhook signature"""
        expected_signature = HMACHelper.generate_webhook_signature(payload, secret)
        return hmac.compare_digest(expected_signature, signature_header)

class SessionHasher:
    """Session token hashing utilities"""
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate session ID"""
        return secrets.token_urlsafe(32)
        
    @staticmethod
    def hash_session_token(session_token: str, user_id: int, 
                          timestamp: datetime = None) -> str:
        """Hash session token with user context"""
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        data = f"{session_token}:{user_id}:{timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()
        
    @staticmethod
    def generate_csrf_token() -> str:
        """Generate CSRF token"""
        return secrets.token_urlsafe(32)
        
    @staticmethod
    def hash_csrf_token(csrf_token: str, session_id: str) -> str:
        """Hash CSRF token with session context"""
        data = f"{csrf_token}:{session_id}"
        return hashlib.sha256(data.encode()).hexdigest()

class DigitalSignature:
    """Digital signature utilities"""
    
    @staticmethod
    def sign_data(data: str, private_key: str) -> str:
        """Create digital signature for data"""
        # This is a simplified example - in production, use proper cryptographic libraries
        signature_data = f"{data}:{private_key}"
        return hashlib.sha256(signature_data.encode()).hexdigest()
        
    @staticmethod
    def verify_signature(data: str, signature: str, public_key: str) -> bool:
        """Verify digital signature"""
        # This is a simplified example - in production, use proper cryptographic libraries
        expected_signature = DigitalSignature.sign_data(data, public_key)
        return hmac.compare_digest(signature, expected_signature)

class PasswordHistory:
    """Password history tracking"""
    
    @staticmethod
    def create_password_history_entry(user_id: int, password_hash: str) -> Dict[str, Any]:
        """Create password history entry"""
        return {
            'user_id': user_id,
            'password_hash': password_hash,
            'created_at': datetime.utcnow(),
            'hash_algorithm': 'bcrypt'
        }
        
    @staticmethod
    def check_password_reuse(new_password: str, 
                           password_history: list, 
                           max_history: int = 5) -> bool:
        """Check if password was used before"""
        for history_entry in password_history[-max_history:]:
            if PasswordHasher.verify_password(new_password, history_entry['password_hash']):
                return True
        return False
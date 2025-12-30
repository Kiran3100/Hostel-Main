"""
Password hashing and verification utilities.

Provides secure password hashing using bcrypt with configurable rounds.
"""

import bcrypt
import logging
from typing import Union

logger = logging.getLogger(__name__)


class PasswordHasher:
    """
    Handle password hashing and verification using bcrypt.
    
    Provides secure password hashing with salt generation and verification.
    Uses bcrypt with configurable rounds for computational cost.
    """
    
    DEFAULT_ROUNDS = 12
    MIN_ROUNDS = 4
    MAX_ROUNDS = 31
    
    def __init__(self, rounds: int = DEFAULT_ROUNDS):
        """
        Initialize password hasher.
        
        Args:
            rounds: Number of bcrypt rounds (4-31, default 12)
            
        Raises:
            ValueError: If rounds is outside valid range
        """
        if not (self.MIN_ROUNDS <= rounds <= self.MAX_ROUNDS):
            raise ValueError(
                f"Rounds must be between {self.MIN_ROUNDS} and {self.MAX_ROUNDS}, got {rounds}"
            )
        
        self.rounds = rounds
        logger.info(f"PasswordHasher initialized with {rounds} rounds")
    
    def hash(self, password: str) -> str:
        """
        Hash a password with salt.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Hashed password as string
            
        Raises:
            ValueError: If password is empty
            TypeError: If password is not a string
        """
        if not isinstance(password, str):
            raise TypeError("Password must be a string")
        
        if not password:
            raise ValueError("Password cannot be empty")
        
        try:
            # Generate salt and hash password
            salt = bcrypt.gensalt(rounds=self.rounds)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            return hashed.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error hashing password: {e}")
            raise
    
    def verify(self, password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password to verify
            hashed_password: Previously hashed password
            
        Returns:
            True if password matches hash, False otherwise
            
        Raises:
            ValueError: If either parameter is empty
            TypeError: If parameters are not strings
        """
        if not isinstance(password, str) or not isinstance(hashed_password, str):
            raise TypeError("Both password and hash must be strings")
        
        if not password or not hashed_password:
            raise ValueError("Password and hash cannot be empty")
        
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.warning(f"Error verifying password: {e}")
            return False
    
    def needs_rehash(self, hashed_password: str) -> bool:
        """
        Check if a hash needs to be rehashed (different rounds).
        
        Args:
            hashed_password: Previously hashed password
            
        Returns:
            True if hash should be regenerated with current rounds
        """
        try:
            return bcrypt.checkpw(b"test", hashed_password.encode('utf-8')) is False
        except Exception:
            # If we can't parse the hash, it should be rehashed
            return True
    
    @classmethod
    def generate_secure_password(cls, length: int = 16) -> str:
        """
        Generate a secure random password.
        
        Args:
            length: Desired password length (minimum 8)
            
        Returns:
            Randomly generated password
        """
        import secrets
        import string
        
        if length < 8:
            raise ValueError("Password length must be at least 8 characters")
        
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
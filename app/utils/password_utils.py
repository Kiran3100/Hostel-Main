"""
Password utilities for hostel management system
Provides password hashing, validation, and generation functionality
"""

from .hashing import PasswordHasher as _PasswordHasher
import secrets
import string
from typing import Dict, Union

class PasswordHelper:
    """
    Password utility class - wrapper around PasswordHasher for backward compatibility
    """
    
    @staticmethod
    def hash_password(password: str, rounds: int = None) -> str:
        """
        Hash password using bcrypt
        
        Args:
            password: Plain text password
            rounds: BCrypt rounds (default: 12)
            
        Returns:
            Hashed password string
        """
        return _PasswordHasher.hash_password(password, rounds)
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Plain text password
            hashed_password: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        return _PasswordHasher.verify_password(password, hashed_password)
    
    @staticmethod
    def needs_rehash(hashed_password: str, rounds: int = None) -> bool:
        """
        Check if password needs rehashing (for upgraded security)
        
        Args:
            hashed_password: Existing hashed password
            rounds: Target rounds (default: 12)
            
        Returns:
            True if rehashing is needed
        """
        return _PasswordHasher.needs_rehash(hashed_password, rounds)
    
    @staticmethod
    def generate_temporary_password(length: int = 12) -> str:
        """
        Generate temporary password
        
        Args:
            length: Password length (default: 12)
            
        Returns:
            Random password string
        """
        return _PasswordHasher.generate_temporary_password(length)
    
    @staticmethod
    def generate_secure_password(
        length: int = 16,
        include_uppercase: bool = True,
        include_lowercase: bool = True,
        include_digits: bool = True,
        include_symbols: bool = True,
        exclude_ambiguous: bool = True
    ) -> str:
        """
        Generate a secure random password
        
        Args:
            length: Password length
            include_uppercase: Include uppercase letters
            include_lowercase: Include lowercase letters
            include_digits: Include digits
            include_symbols: Include special characters
            exclude_ambiguous: Exclude ambiguous characters (il1Lo0O)
            
        Returns:
            Generated password
        """
        if length < 4:
            length = 4
        
        # Build character set
        charset = ""
        required_chars = []
        
        # Ambiguous characters to exclude
        ambiguous = 'il1Lo0O'
        
        if include_uppercase:
            uppercase = string.ascii_uppercase
            if exclude_ambiguous:
                uppercase = ''.join(c for c in uppercase if c not in ambiguous)
            charset += uppercase
            if uppercase:
                required_chars.append(secrets.choice(uppercase))
        
        if include_lowercase:
            lowercase = string.ascii_lowercase
            if exclude_ambiguous:
                lowercase = ''.join(c for c in lowercase if c not in ambiguous)
            charset += lowercase
            if lowercase:
                required_chars.append(secrets.choice(lowercase))
        
        if include_digits:
            digits = string.digits
            if exclude_ambiguous:
                digits = ''.join(c for c in digits if c not in ambiguous)
            charset += digits
            if digits:
                required_chars.append(secrets.choice(digits))
        
        if include_symbols:
            symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?'
            charset += symbols
            required_chars.append(secrets.choice(symbols))
        
        if not charset:
            charset = string.ascii_letters + string.digits
        
        # Generate remaining characters
        remaining_length = max(0, length - len(required_chars))
        password_chars = required_chars + [secrets.choice(charset) for _ in range(remaining_length)]
        
        # Shuffle to avoid predictable pattern
        import random
        random.shuffle(password_chars)
        
        return ''.join(password_chars)
    
    @staticmethod
    def check_password_strength(password: str) -> Dict[str, Union[int, bool, str, list]]:
        """
        Check password strength and return detailed analysis
        
        Args:
            password: Password to check
            
        Returns:
            Dictionary with strength analysis
        """
        result = {
            'score': 0,
            'length': len(password) if password else 0,
            'has_uppercase': False,
            'has_lowercase': False,
            'has_digits': False,
            'has_symbols': False,
            'strength': 'very_weak',
            'feedback': []
        }
        
        if not password:
            result['feedback'].append('Password is empty')
            return result
        
        # Check character types
        if any(c.isupper() for c in password):
            result['has_uppercase'] = True
            result['score'] += 1
        else:
            result['feedback'].append('Add uppercase letters')
        
        if any(c.islower() for c in password):
            result['has_lowercase'] = True
            result['score'] += 1
        else:
            result['feedback'].append('Add lowercase letters')
        
        if any(c.isdigit() for c in password):
            result['has_digits'] = True
            result['score'] += 1
        else:
            result['feedback'].append('Add digits')
        
        if any(c in string.punctuation for c in password):
            result['has_symbols'] = True
            result['score'] += 1
        else:
            result['feedback'].append('Add special characters')
        
        # Length scoring
        length = len(password)
        if length >= 16:
            result['score'] += 3
        elif length >= 12:
            result['score'] += 2
        elif length >= 8:
            result['score'] += 1
        else:
            result['feedback'].append('Use at least 8 characters (12+ recommended)')
        
        # Determine strength
        if result['score'] <= 2:
            result['strength'] = 'very_weak'
        elif result['score'] <= 4:
            result['strength'] = 'weak'
        elif result['score'] <= 6:
            result['strength'] = 'medium'
        elif result['score'] <= 7:
            result['strength'] = 'strong'
        else:
            result['strength'] = 'very_strong'
        
        # Check for common patterns
        common_passwords = [
            'password', '123456', 'qwerty', 'admin', 'letmein',
            'welcome', 'monkey', 'password123', '12345678'
        ]
        
        if password.lower() in common_passwords:
            result['score'] = 0
            result['strength'] = 'very_weak'
            result['feedback'].append('This is a commonly used password')
        
        # Check for sequential characters
        if any(password[i:i+3].lower() in 'abcdefghijklmnopqrstuvwxyz' for i in range(len(password)-2)):
            result['feedback'].append('Avoid sequential letters')
        
        if any(password[i:i+3] in '0123456789' for i in range(len(password)-2)):
            result['feedback'].append('Avoid sequential numbers')
        
        return result
    
    @staticmethod
    def validate_password(password: str, min_length: int = 8, 
                         require_uppercase: bool = True,
                         require_lowercase: bool = True,
                         require_digits: bool = True,
                         require_symbols: bool = True) -> tuple[bool, list]:
        """
        Validate password against requirements
        
        Args:
            password: Password to validate
            min_length: Minimum password length
            require_uppercase: Require uppercase letters
            require_lowercase: Require lowercase letters
            require_digits: Require digits
            require_symbols: Require special characters
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        if not password:
            errors.append('Password is required')
            return False, errors
        
        if len(password) < min_length:
            errors.append(f'Password must be at least {min_length} characters long')
        
        if require_uppercase and not any(c.isupper() for c in password):
            errors.append('Password must contain at least one uppercase letter')
        
        if require_lowercase and not any(c.islower() for c in password):
            errors.append('Password must contain at least one lowercase letter')
        
        if require_digits and not any(c.isdigit() for c in password):
            errors.append('Password must contain at least one digit')
        
        if require_symbols and not any(c in string.punctuation for c in password):
            errors.append('Password must contain at least one special character')
        
        return len(errors) == 0, errors
    
    @staticmethod
    def generate_reset_token(length: int = 32) -> str:
        """
        Generate password reset token
        
        Args:
            length: Token length
            
        Returns:
            URL-safe random token
        """
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_verification_code(length: int = 6, numeric_only: bool = True) -> str:
        """
        Generate verification code (for email/SMS verification)
        
        Args:
            length: Code length
            numeric_only: Use only numbers (default: True)
            
        Returns:
            Verification code
        """
        if numeric_only:
            return ''.join(secrets.choice(string.digits) for _ in range(length))
        else:
            # Alphanumeric excluding ambiguous characters
            charset = string.ascii_uppercase + string.digits
            charset = ''.join(c for c in charset if c not in 'IL10O')
            return ''.join(secrets.choice(charset) for _ in range(length))


__all__ = ['PasswordHelper']
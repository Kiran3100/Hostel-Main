import hashlib
import secrets
import time
from typing import Dict, List, Optional, Tuple
from passlib.context import CryptContext
from passlib.hash import bcrypt
import re
import logging

logger = logging.getLogger(__name__)

class PasswordHasher:
    """Password hashing and verification utility"""
    
    def __init__(self):
        # Configure password context with multiple schemes for flexibility
        self.pwd_context = CryptContext(
            schemes=["bcrypt", "pbkdf2_sha256"],
            default="bcrypt",
            bcrypt__rounds=12,
            pbkdf2_sha256__rounds=30000,
            deprecated="auto"
        )
        
        # Salt configuration
        self.salt_length = 32
        self.pepper = self._get_pepper()
    
    def hash_password(self, password: str) -> str:
        """Hash password with salt and pepper"""
        try:
            # Add pepper to password
            peppered_password = self._add_pepper(password)
            
            # Hash using passlib
            hashed = self.pwd_context.hash(peppered_password)
            
            logger.debug("Password hashed successfully")
            return hashed
            
        except Exception as e:
            logger.error(f"Password hashing failed: {str(e)}")
            raise ValueError("Password hashing failed")
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            # Add pepper to provided password
            peppered_password = self._add_pepper(password)
            
            # Verify using passlib
            is_valid = self.pwd_context.verify(peppered_password, hashed_password)
            
            # Check if hash needs updating (e.g., rounds increased)
            if is_valid and self.pwd_context.needs_update(hashed_password):
                logger.info("Password hash needs updating")
                # Return tuple indicating update needed
                return (True, True)
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Password verification failed: {str(e)}")
            return False
    
    def _add_pepper(self, password: str) -> str:
        """Add pepper to password for additional security"""
        return password + self.pepper
    
    def _get_pepper(self) -> str:
        """Get pepper from environment or config"""
        # In production, this should come from secure configuration
        return "hostel_management_pepper_2024"
    
    def update_hash(self, password: str, old_hash: str) -> Optional[str]:
        """Update password hash if needed (e.g., rounds changed)"""
        if self.pwd_context.needs_update(old_hash):
            return self.hash_password(password)
        return None

class PasswordValidator:
    """Password strength validation utility"""
    
    def __init__(self):
        self.min_length = 8
        self.max_length = 128
        self.require_uppercase = True
        self.require_lowercase = True
        self.require_numbers = True
        self.require_special_chars = True
        self.min_special_chars = 1
        
        # Common weak passwords
        self.common_passwords = self._load_common_passwords()
        
        # Pattern definitions
        self.patterns = {
            'uppercase': re.compile(r'[A-Z]'),
            'lowercase': re.compile(r'[a-z]'),
            'numbers': re.compile(r'[0-9]'),
            'special': re.compile(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\/?]'),
            'spaces': re.compile(r'\s'),
        }
    
    def validate_password(self, password: str, user_info: Optional[Dict] = None) -> Dict[str, any]:
        """Comprehensive password validation"""
        validation_result = {
            'is_valid': True,
            'score': 0,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }
        
        # Length validation
        if len(password) < self.min_length:
            validation_result['is_valid'] = False
            validation_result['errors'].append(
                f"Password must be at least {self.min_length} characters long"
            )
        
        if len(password) > self.max_length:
            validation_result['is_valid'] = False
            validation_result['errors'].append(
                f"Password must not exceed {self.max_length} characters"
            )
        
        # Character type validation
        if self.require_uppercase and not self.patterns['uppercase'].search(password):
            validation_result['is_valid'] = False
            validation_result['errors'].append("Password must contain at least one uppercase letter")
        
        if self.require_lowercase and not self.patterns['lowercase'].search(password):
            validation_result['is_valid'] = False
            validation_result['errors'].append("Password must contain at least one lowercase letter")
        
        if self.require_numbers and not self.patterns['numbers'].search(password):
            validation_result['is_valid'] = False
            validation_result['errors'].append("Password must contain at least one number")
        
        if self.require_special_chars:
            special_matches = self.patterns['special'].findall(password)
            if len(special_matches) < self.min_special_chars:
                validation_result['is_valid'] = False
                validation_result['errors'].append(
                    f"Password must contain at least {self.min_special_chars} special character(s)"
                )
        
        # Check for spaces
        if self.patterns['spaces'].search(password):
            validation_result['warnings'].append("Password contains spaces")
        
        # Common password check
        if password.lower() in self.common_passwords:
            validation_result['is_valid'] = False
            validation_result['errors'].append("Password is too common")
        
        # Personal information check
        if user_info:
            if self._contains_personal_info(password, user_info):
                validation_result['is_valid'] = False
                validation_result['errors'].append("Password must not contain personal information")
        
        # Calculate password strength score
        validation_result['score'] = self._calculate_strength_score(password)
        
        # Add suggestions for improvement
        validation_result['suggestions'] = self._generate_suggestions(password, validation_result)
        
        return validation_result
    
    def _calculate_strength_score(self, password: str) -> int:
        """Calculate password strength score (0-100)"""
        score = 0
        
        # Length scoring
        if len(password) >= 8:
            score += 20
        if len(password) >= 12:
            score += 10
        if len(password) >= 16:
            score += 10
        
        # Character variety scoring
        if self.patterns['lowercase'].search(password):
            score += 10
        if self.patterns['uppercase'].search(password):
            score += 10
        if self.patterns['numbers'].search(password):
            score += 10
        if self.patterns['special'].search(password):
            score += 15
        
        # Complexity patterns
        unique_chars = len(set(password))
        if unique_chars > len(password) * 0.7:
            score += 10
        
        # Avoid repetitive patterns
        if not self._has_repetitive_patterns(password):
            score += 5
        
        return min(score, 100)
    
    def _contains_personal_info(self, password: str, user_info: Dict) -> bool:
        """Check if password contains personal information"""
        password_lower = password.lower()
        
        # Check common personal information fields
        personal_fields = ['first_name', 'last_name', 'email', 'username', 'phone']
        
        for field in personal_fields:
            if field in user_info and user_info[field]:
                value = str(user_info[field]).lower()
                if len(value) > 2 and value in password_lower:
                    return True
        
        return False
    
    def _has_repetitive_patterns(self, password: str) -> bool:
        """Check for repetitive patterns in password"""
        # Check for repeated characters
        for i in range(len(password) - 2):
            if password[i] == password[i+1] == password[i+2]:
                return True
        
        # Check for sequential patterns
        for i in range(len(password) - 2):
            if (ord(password[i+1]) == ord(password[i]) + 1 and 
                ord(password[i+2]) == ord(password[i]) + 2):
                return True
        
        return False
    
    def _generate_suggestions(self, password: str, validation_result: Dict) -> List[str]:
        """Generate suggestions for password improvement"""
        suggestions = []
        
        if validation_result['score'] < 60:
            suggestions.append("Consider using a longer password (12+ characters)")
            suggestions.append("Mix uppercase and lowercase letters")
            suggestions.append("Include numbers and special characters")
            suggestions.append("Avoid common words and patterns")
        
        if not self.patterns['special'].search(password):
            suggestions.append("Add special characters like !@#$%^&*")
        
        if len(password) < 12:
            suggestions.append("Use at least 12 characters for better security")
        
        return suggestions
    
    def _load_common_passwords(self) -> set:
        """Load list of common passwords"""
        # In production, this would load from a file
        return {
            'password', '123456', 'password123', 'admin', 'qwerty',
            'letmein', 'welcome', 'monkey', 'dragon', 'master',
            '123456789', 'iloveyou', 'password1', 'admin123'
        }

class PasswordHistoryManager:
    """Password history and reuse prevention"""
    
    def __init__(self, history_size: int = 5):
        self.history_size = history_size
        self.password_hasher = PasswordHasher()
    
    def check_password_reuse(self, user_id: str, new_password: str, password_history: List[str]) -> bool:
        """Check if password was used recently"""
        for old_hash in password_history[-self.history_size:]:
            if self.password_hasher.verify_password(new_password, old_hash):
                return True
        return False
    
    def add_to_history(self, password_history: List[str], new_password_hash: str) -> List[str]:
        """Add new password hash to history"""
        updated_history = password_history.copy()
        updated_history.append(new_password_hash)
        
        # Keep only recent passwords
        if len(updated_history) > self.history_size:
            updated_history = updated_history[-self.history_size:]
        
        return updated_history

class PasswordPolicyEnforcer:
    """Password policy enforcement utility"""
    
    def __init__(self):
        self.policies = {
            'min_length': 8,
            'max_age_days': 90,
            'warning_days': 7,
            'history_size': 5,
            'complexity_required': True,
            'lockout_attempts': 5,
            'lockout_duration_minutes': 30
        }
    
    def enforce_policy(self, user_id: str, password: str, user_data: Dict) -> Dict[str, any]:
        """Enforce password policy for user"""
        result = {
            'policy_compliant': True,
            'violations': [],
            'warnings': [],
            'actions_required': []
        }
        
        # Check password age
        last_changed = user_data.get('password_last_changed')
        if last_changed:
            days_since_change = (time.time() - last_changed) / 86400
            
            if days_since_change > self.policies['max_age_days']:
                result['policy_compliant'] = False
                result['violations'].append("Password has expired")
                result['actions_required'].append("change_password")
            
            elif days_since_change > (self.policies['max_age_days'] - self.policies['warning_days']):
                result['warnings'].append(
                    f"Password will expire in {self.policies['max_age_days'] - int(days_since_change)} days"
                )
        
        # Check password complexity if required
        if self.policies['complexity_required']:
            validator = PasswordValidator()
            validation = validator.validate_password(password, user_data)
            
            if not validation['is_valid']:
                result['policy_compliant'] = False
                result['violations'].extend(validation['errors'])
        
        # Check password history
        password_history = user_data.get('password_history', [])
        history_manager = PasswordHistoryManager(self.policies['history_size'])
        
        if history_manager.check_password_reuse(user_id, password, password_history):
            result['policy_compliant'] = False
            result['violations'].append("Password was used recently")
        
        return result
    
    def check_account_lockout(self, failed_attempts: int, last_attempt_time: float) -> Dict[str, any]:
        """Check if account should be locked due to failed attempts"""
        result = {
            'is_locked': False,
            'remaining_attempts': self.policies['lockout_attempts'] - failed_attempts,
            'unlock_time': None
        }
        
        if failed_attempts >= self.policies['lockout_attempts']:
            lockout_duration = self.policies['lockout_duration_minutes'] * 60
            unlock_time = last_attempt_time + lockout_duration
            
            if time.time() < unlock_time:
                result['is_locked'] = True
                result['unlock_time'] = unlock_time
                result['remaining_attempts'] = 0
            else:
                # Lockout period expired
                result['remaining_attempts'] = self.policies['lockout_attempts']
        
        return result

class SecureRandomGenerator:
    """Cryptographically secure random generator"""
    
    @staticmethod
    def generate_password(length: int = 12, include_symbols: bool = True) -> str:
        """Generate cryptographically secure random password"""
        lowercase = 'abcdefghijklmnopqrstuvwxyz'
        uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        digits = '0123456789'
        symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?'
        
        # Ensure password contains at least one character from each category
        password_chars = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits)
        ]
        
        if include_symbols:
            password_chars.append(secrets.choice(symbols))
            all_chars = lowercase + uppercase + digits + symbols
        else:
            all_chars = lowercase + uppercase + digits
        
        # Fill remaining length with random characters
        for _ in range(length - len(password_chars)):
            password_chars.append(secrets.choice(all_chars))
        
        # Shuffle the password characters
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_salt(length: int = 32) -> bytes:
        """Generate cryptographically secure salt"""
        return secrets.token_bytes(length)
    
    @staticmethod
    def generate_hex_token(length: int = 32) -> str:
        """Generate cryptographically secure hex token"""
        return secrets.token_hex(length)

class SaltGenerator:
    """Password salt generation utility"""
    
    def __init__(self, salt_length: int = 32):
        self.salt_length = salt_length
    
    def generate_salt(self) -> str:
        """Generate base64 encoded salt"""
        salt_bytes = secrets.token_bytes(self.salt_length)
        return salt_bytes.hex()
    
    def generate_salt_for_user(self, user_id: str) -> str:
        """Generate deterministic salt based on user ID"""
        # Mix user ID with random salt for uniqueness
        random_salt = secrets.token_bytes(16)
        combined = user_id.encode() + random_salt
        
        # Hash to create deterministic but unique salt
        salt_hash = hashlib.sha256(combined).hexdigest()
        return salt_hash[:self.salt_length]
    
    def verify_salt_format(self, salt: str) -> bool:
        """Verify salt format is correct"""
        try:
            # Check if it's valid hex
            bytes.fromhex(salt)
            return len(salt) == self.salt_length * 2  # Hex is double the byte length
        except ValueError:
            return False
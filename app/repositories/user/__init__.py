"""
User repositories package initialization.

This package provides comprehensive repository layer for user management,
including authentication, profiles, addresses, emergency contacts, sessions,
security tracking, and aggregate operations.
"""

from app.repositories.user.user_repository import UserRepository
from app.repositories.user.user_profile_repository import UserProfileRepository
from app.repositories.user.user_address_repository import UserAddressRepository
from app.repositories.user.emergency_contact_repository import EmergencyContactRepository
from app.repositories.user.user_session_repository import UserSessionRepository
from app.repositories.user.user_aggregate_repository import UserAggregateRepository
from app.repositories.user.user_security_repository import UserSecurityRepository

__all__ = [
    # Core user management
    "UserRepository",
    "UserProfileRepository",
    "UserAddressRepository",
    "EmergencyContactRepository",
    
    # Session management
    "UserSessionRepository",
    
    # Aggregate operations
    "UserAggregateRepository",
    
    # Security tracking
    "UserSecurityRepository",
]


# Repository usage examples and patterns
"""
USAGE EXAMPLES:

1. Basic User Operations:
-----------------------
from app.repositories.user import UserRepository

user_repo = UserRepository(db)

# Find user by email
user = user_repo.find_by_email("user@example.com")

# Create new user
user_data = {
    "email": "new@example.com",
    "phone": "+1234567890",
    "full_name": "John Doe",
    "password_hash": hashed_password,
    "user_role": UserRole.STUDENT
}
new_user = user_repo.create(user_data)

# Update login success
user_repo.update_login_success(user.id, ip_address="192.168.1.1")

# Search users
users, total = user_repo.search_users(
    search_term="john",
    role=UserRole.STUDENT,
    is_active=True,
    limit=20
)


2. Profile Management:
---------------------
from app.repositories.user import UserProfileRepository

profile_repo = UserProfileRepository(db)

# Get or create profile
profile = profile_repo.create_or_update(
    user_id=user.id,
    profile_data={
        "gender": Gender.MALE,
        "date_of_birth": date(2000, 1, 1),
        "bio": "Student profile"
    }
)

# Update completion percentage
profile = profile_repo.update_completion_percentage(user.id)

# Find incomplete profiles
incomplete = profile_repo.find_incomplete_profiles(max_completion=50)


3. Address Management:
---------------------
from app.repositories.user import UserAddressRepository

address_repo = UserAddressRepository(db)

# Create address
address = address_repo.create({
    "user_id": user.id,
    "address_type": "home",
    "address_line1": "123 Main St",
    "city": "New York",
    "state": "NY",
    "pincode": "10001",
    "country": "USA"
})

# Set as primary
address_repo.set_primary_address(address.id, user.id)

# Find addresses within radius
nearby = address_repo.find_within_radius(
    center_lat=40.7128,
    center_lon=-74.0060,
    radius_km=10
)


4. Emergency Contacts:
---------------------
from app.repositories.user import EmergencyContactRepository

contact_repo = EmergencyContactRepository(db)

# Create emergency contact
contact = contact_repo.create({
    "user_id": user.id,
    "emergency_contact_name": "Jane Doe",
    "emergency_contact_phone": "+1234567890",
    "emergency_contact_relation": "Mother",
    "priority": 1,
    "is_primary": True
})

# Verify contact
contact_repo.verify_contact(contact.id, verification_method="phone_call")

# Log contact attempt
contact_repo.log_contact_attempt(contact.id, success=True)


5. Session Management:
---------------------
from app.repositories.user import UserSessionRepository

session_repo = UserSessionRepository(db)

# Create session
session = session_repo.create_session(
    user_id=user.id,
    refresh_token_hash=token_hash,
    expires_at=expiry_time,
    ip_address="192.168.1.1",
    device_info={"browser": "Chrome", "os": "Windows"}
)

# Update activity
session_repo.update_last_activity(session.id)

# Revoke session
session_repo.revoke_session(
    session.id,
    reason="user_logout"
)

# Cleanup expired
count = session_repo.cleanup_expired_sessions()


6. Security Tracking:
--------------------
from app.repositories.user import UserSecurityRepository

security_repo = UserSecurityRepository(db)

# Log login attempt
login_record = security_repo.create_login_attempt(
    user_id=user.id,
    email_attempted=user.email,
    is_successful=True,
    ip_address="192.168.1.1",
    auth_method="password"
)

# Check for brute force
is_attack = security_repo.detect_brute_force_attempt(
    email=user.email,
    minutes=15,
    threshold=5
)

# Create password history
security_repo.create_password_history(
    user_id=user.id,
    password_hash=new_hash,
    change_reason="user_request"
)

# Check password reuse
is_reused = security_repo.check_password_reuse(
    user_id=user.id,
    new_password_hash=new_hash,
    history_limit=5
)


7. Aggregate Operations:
-----------------------
from app.repositories.user import UserAggregateRepository

aggregate_repo = UserAggregateRepository(db)

# Get complete user data
complete_user = aggregate_repo.get_complete_user(user.id)

# Advanced search
users, total = aggregate_repo.advanced_user_search(
    search_term="john",
    role=UserRole.STUDENT,
    city="New York",
    min_profile_completion=50,
    limit=20
)

# Platform overview
overview = aggregate_repo.get_platform_overview()

# Growth metrics
growth = aggregate_repo.get_user_growth_metrics(days=30)

# Security overview
security = aggregate_repo.get_security_overview()


8. Analytics & Reports:
----------------------
# User statistics
stats = user_repo.get_user_statistics()

# Profile statistics
profile_stats = profile_repo.get_profile_statistics()

# Geographic distribution
geo_dist = address_repo.get_geographic_distribution()

# Login statistics
login_stats = security_repo.get_login_statistics(days=30)

# Engagement metrics
engagement = aggregate_repo.get_engagement_metrics()


BEST PRACTICES:
--------------

1. Transaction Management:
   - Use database sessions appropriately
   - Commit after successful operations
   - Rollback on errors

2. Error Handling:
   - Catch EntityNotFoundError for missing records
   - Validate input data before operations
   - Use appropriate exception types

3. Performance:
   - Use eager loading for related entities
   - Implement pagination for large result sets
   - Cache frequently accessed data
   - Use bulk operations when possible

4. Security:
   - Never expose password hashes
   - Log all security-relevant operations
   - Implement rate limiting for sensitive operations
   - Validate all user inputs

5. Data Integrity:
   - Use transactions for multi-step operations
   - Validate foreign key relationships
   - Implement soft deletes where appropriate
   - Maintain audit trails
"""
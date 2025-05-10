from app.models.user import User
from app.schemas.user_schemas import UserCreateRequest
from datetime import datetime

class UserRepository:
    """Repository class for User-related operations."""

    def __init__(self):
        pass
        
    @staticmethod
    def create_user(request: UserCreateRequest) -> User:
        """Create a new user in the database."""
        
        user = User(
            firstName=request.firstName,
            lastName=request.lastName,
            email=request.email,
            password=request.password,
            handle=request.handle,
            dateOfBirth=request.dateOfBirth
        )
        user.save()
        return user

    @staticmethod
    def find_user_by_email(email: str) -> User:
        """Find a user by email."""
        return User.objects(email=email).first()
        
    @staticmethod
    def find_user_by_id(user_id: str) -> User:
        """Find a user by ID."""
        return User.objects(id=user_id).first()
    
    @staticmethod
    def delete_user(self, user_id: str) -> bool:
        """Delete a user logically by ID."""
        user = self.find_user_by_id(user_id)

        user.deleted = True
        user.deleted_at = datetime.utcnow()

        user.save()
        return True
    
    def delete_user_oblivion(self, user_id: str) -> bool:
        """Obscure all the user information and delete the user logically."""
        user = self.find_user_by_id(user_id)

        user.firstName = "Deleted"
        user.lastName = "User"
        user.email = "redacted"
        user.handle = f"deleted_{user_id}"
        user.dateOfBirth = None
        user.deleted = True
        user.deleted_at = datetime.utcnow()
        user.save()

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.logging_config import logger

USERS_FILE_PATH = os.environ.get("USERS_FILE_PATH") or str(
    Path(__file__).resolve().parents[2] / "data" / "users.json"
)

def _hash_password(password: str) -> str:
    """Hash password using SHA-256 with a salt."""
    salt = "atlas_sec_salt_2026"
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, storage_path: str = USERS_FILE_PATH):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Create users.json with initial admin officer if not present."""
        if not self.storage_path.exists():
            default_users = [
                {
                    "badgeNumber": "IND-LE-8402",
                    "officerName": "Rahul Sharma",
                    "passwordHash": _hash_password("admin123"),
                    "department": "Special Crime & Anti-Extortion Unit",
                    "clearanceLevel": "Level 3: Lead Detective",
                    "createdAt": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            ]
            self._save_users(default_users)

    def _load_users(self) -> List[Dict[str, Any]]:
        """Load all users from disk."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading users file: {e}")
        return []

    def _save_users(self, users: List[Dict[str, Any]]) -> None:
        """Save users list to disk."""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving users file: {e}")

    def register(
        self,
        officer_name: str,
        badge_number: str,
        password: str,
        department: str = "Special Crime & Anti-Extortion Unit",
        clearance_level: str = "Level 3: Lead Detective"
    ) -> Dict[str, Any]:
        """Register a new officer user."""
        officer_name = officer_name.strip()
        badge_number = badge_number.strip().upper()
        if not officer_name:
            raise ValueError("Officer name is required.")
        if not badge_number:
            raise ValueError("Badge number is required.")
        if not password or len(password) < 4:
            raise ValueError("Password must be at least 4 characters long.")

        users = self._load_users()
        # Check duplicate badge or name
        for u in users:
            if u.get("badgeNumber", "").upper() == badge_number:
                raise ValueError(f"Officer with badge number '{badge_number}' is already registered.")
            if u.get("officerName", "").strip().lower() == officer_name.lower():
                raise ValueError(f"Officer with name '{officer_name}' is already registered.")

        new_user = {
            "badgeNumber": badge_number,
            "officerName": officer_name,
            "passwordHash": _hash_password(password),
            "department": department or "Special Crime & Anti-Extortion Unit",
            "clearanceLevel": clearance_level or "Level 3: Lead Detective",
            "createdAt": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        users.append(new_user)
        self._save_users(users)

        logger.info(f"Registered new officer: {officer_name} ({badge_number})")
        return {
            "badgeNumber": badge_number,
            "officerName": officer_name,
            "department": new_user["department"],
            "clearanceLevel": new_user["clearanceLevel"],
            "signedInAt": time.strftime("%I:%M:%S %p")
        }

    def login(self, identifier: str, password: str) -> Dict[str, Any]:
        """Authenticate an officer by badge number or name."""
        clean_id = identifier.strip()
        if not clean_id or not password:
            raise ValueError("Badge ID / Officer Name and Password are required.")

        users = self._load_users()
        pass_hash = _hash_password(password)

        matched_user = None
        for u in users:
            if (u.get("badgeNumber", "").upper() == clean_id.upper() or
                u.get("officerName", "").strip().lower() == clean_id.lower()):
                matched_user = u
                break

        if not matched_user:
            raise ValueError("Officer credential record not found. Please register / sign up first.")

        if matched_user.get("passwordHash") != pass_hash:
            raise ValueError("Invalid passcode for the specified officer.")

        logger.info(f"Officer logged in successfully: {matched_user['officerName']} ({matched_user['badgeNumber']})")
        return {
            "badgeNumber": matched_user["badgeNumber"],
            "officerName": matched_user["officerName"],
            "department": matched_user.get("department", "Special Crime & Anti-Extortion Unit"),
            "clearanceLevel": matched_user.get("clearanceLevel", "Level 3: Lead Detective"),
            "signedInAt": time.strftime("%I:%M:%S %p")
        }

    def list_users(self) -> List[Dict[str, Any]]:
        """List all registered officers without sensitive hashes."""
        users = self._load_users()
        return [
            {
                "badgeNumber": u.get("badgeNumber"),
                "officerName": u.get("officerName"),
                "department": u.get("department"),
                "clearanceLevel": u.get("clearanceLevel"),
                "createdAt": u.get("createdAt")
            }
            for u in users
        ]


auth_service = AuthService()

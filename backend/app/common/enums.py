from enum import StrEnum


class RoleCode(StrEnum):
    CUSTOMER = "CUSTOMER"
    MERCHANT_OWNER = "MERCHANT_OWNER"
    MERCHANT_CASHIER = "MERCHANT_CASHIER"
    MERCHANT_ANALYST = "MERCHANT_ANALYST"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISABLED = "disabled"


class MerchantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class WorkspaceType(StrEnum):
    CUSTOMER = "customer"
    MERCHANT = "merchant"

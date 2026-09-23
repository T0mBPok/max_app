import enum


class ActivityType(enum.StrEnum):
    EVENT = "EVENT"
    SECTION = "SECTION"
    COURSE = "COURSE"
    VOLUNTEERING = "VOLUNTEERING"


class ActivityStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    ARCHIVED = "ARCHIVED"
    CANCELLED = "CANCELLED"


class UserStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"


class ImportStatus(enum.StrEnum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class AgePreset(enum.StrEnum):
    ALL = "ALL"
    TEENS_12_17 = "TEENS_12_17"
    YOUTH_18_24 = "YOUTH_18_24"
    ADULTS_25_39 = "ADULTS_25_39"
    ADULTS_40_59 = "ADULTS_40_59"
    SENIORS_60_PLUS = "SENIORS_60_PLUS"
    ALL_ADULTS_18_PLUS = "ALL_ADULTS_18_PLUS"
    CUSTOM = "CUSTOM"


class JoinPolicy(enum.StrEnum):
    OPEN = "OPEN"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"


class RoomStatus(enum.StrEnum):
    OPEN = "OPEN"
    FULL = "FULL"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class MemberRole(enum.StrEnum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"


class MemberStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    LEFT = "LEFT"
    REMOVED = "REMOVED"


class JoinRequestStatus(enum.StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

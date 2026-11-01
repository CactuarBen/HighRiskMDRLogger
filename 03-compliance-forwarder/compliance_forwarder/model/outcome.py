from enum import Enum


class Outcome(str, Enum):
    SENT = "sent"
    REJECTED = "rejected"
    RETRY = "retry"

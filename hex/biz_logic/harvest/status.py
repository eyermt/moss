from enum import Enum
class Status(str, Enum):
    in_progress = "In Progress"
    finished = "Finished"
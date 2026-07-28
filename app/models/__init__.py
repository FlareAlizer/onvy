"""ORM-модели. Импортируются здесь, чтобы зарегистрироваться в Base.metadata."""

from app.models.analysis import DialogueAnalysis
from app.models.assistant_log import AssistantLog
from app.models.course import Course, CourseProgress
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.goal import Goal
from app.models.message import Message
from app.models.product import Product

__all__ = [
    "AssistantLog",
    "Course",
    "CourseProgress",
    "Department",
    "DialogueAnalysis",
    "Employee",
    "Role",
    "Goal",
    "Message",
    "Product",
]

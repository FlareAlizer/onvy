"""ORM-модели домена чайханы.

Импортируются здесь, чтобы зарегистрироваться в Base.metadata — это нужно
и Alembic autogenerate, и для явного единого списка сущностей домена.
"""

from app.db.models.assistant_query import AssistantQuery, AssistantQueryMenuItem
from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.menu_item import MenuItem
from app.db.models.metric_snapshot import MetricSnapshot
from app.db.models.stop_list_entry import StopListEntry
from app.db.models.utterance import Utterance
from app.db.models.venue import Venue

__all__ = [
    "AssistantQuery",
    "AssistantQueryMenuItem",
    "CommGroup",
    "Employee",
    "EmployeeCommGroup",
    "MenuItem",
    "MetricSnapshot",
    "StopListEntry",
    "Utterance",
    "Venue",
]

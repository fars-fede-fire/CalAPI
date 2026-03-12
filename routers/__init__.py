from .upload import router as upload_router
from .categories import router as categories_router
from .shift_types import router as shift_types_router
from .raw_shifts import router as raw_shifts_router
from .employees import router as employees_router
from .calendar import router as calendar_router
from .config_io import router as config_io_router
from .auth import router as auth_router

__all__ = [
    "upload_router",
    "categories_router",
    "shift_types_router",
    "raw_shifts_router",
    "employees_router",
    "calendar_router",
    "config_io_router",
    "auth_router"
]
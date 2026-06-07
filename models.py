from pydantic import BaseModel
from typing import Optional


class CommandResult(BaseModel):
    status: str
    result: Optional[str] = None
    message: Optional[str] = None
    user_id: str
    screenshot: Optional[str] = None

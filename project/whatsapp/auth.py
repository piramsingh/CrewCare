"""
Placeholder auth dependency. Replace with your real session/JWT-based
`get_current_employee_id` so linking/unlink endpoints are only ever callable
by an authenticated worker acting on their own account — never trust a
client-supplied employee_id in the request body for these endpoints.
"""
from fastapi import Header, HTTPException


def get_current_employee_id(x_demo_employee_id: str = Header(...)) -> str:
    """DEMO ONLY: reads the employee id from a header so this module runs
    standalone. Replace with real auth (e.g. decode a JWT / session cookie
    and return the authenticated user's employee_id) before shipping."""
    if not x_demo_employee_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return x_demo_employee_id

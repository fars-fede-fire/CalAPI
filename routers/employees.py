from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models import Employee
from schemas import EmployeeRead

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("", response_model=list[EmployeeRead])
def list_employees(session: Session = Depends(get_session)):
    return session.exec(select(Employee).order_by(Employee.name)).all()


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(employee_id: int, session: Session = Depends(get_session)):
    emp = session.get(Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Medarbejder ikke fundet.")
    return emp

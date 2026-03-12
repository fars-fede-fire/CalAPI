from calendar import monthrange
from datetime import datetime, timedelta, date
from io import BytesIO
import pandas as pd


class ExcelParser:
    def __init__(self, file_bytes: bytes):
        self.file_bytes = file_bytes
        self.df: pd.DataFrame | None = None
        self.start_date: datetime | None = None
        self.end_date: datetime | None = None
        self.list_of_employees: list[str] | None = None

    def parse(self) -> None:
        self._load_dataframe()
        self._extract_month()
        self._add_date_column()
        self._get_employees()

    def get_employees(self) -> list[str]:
        return self.list_of_employees

    def get_raw_shift_types(self, employees: list[str]) -> list[str]:
        list_of_raw_shifts = []
        for employee in employees:
            if employee in self.df.columns:
                self.df[employee] = self.df[employee].fillna("NaN")
                self.df[employee] = self.df[employee].astype(dtype="str")
                self.df[employee] = self.df[employee].str.upper().str.strip()
            if employee in self.df.columns:
                for item in self.df[employee].unique():
                    if item not in list_of_raw_shifts:
                        list_of_raw_shifts.append(item)
        return list_of_raw_shifts

    def dataframe_to_shift(self, employees: list[str]) -> list[dict]:
        shifts = []
        for employee in employees:
            if employee in self.df.columns:
                col = self.df[employee].fillna("NaN").astype(str).str.upper().str.strip()
                for idx, row in self.df.iterrows():
                    shift_date = row["DATE"]
                    raw_shift = col.iloc[idx] if isinstance(idx, int) else col[idx]
                    shift = {
                        "date": shift_date.date() if hasattr(shift_date, "date") else shift_date,
                        "employee": employee,
                        "raw_shift": raw_shift,
                    }
                    shifts.append(shift)
        return shifts

    def _load_dataframe(self):
        file_like = BytesIO(self.file_bytes)
        self.df = pd.read_excel(file_like)

    def _extract_month(self):
        cell = self.df.columns[0]
        if isinstance(cell, datetime):
            self.start_date = cell
            self.end_date = datetime(
                year=self.start_date.year,
                month=self.start_date.month,
                day=monthrange(self.start_date.year, self.start_date.month)[1],
            )
            return
        raise TypeError("Filen indeholder forkert datoformat i første celle/kolonne.")

    def _add_date_column(self):
        last_day_in_month = monthrange(self.start_date.year, self.start_date.month)[1]
        self.df = self.df.iloc[:last_day_in_month].reset_index(drop=True)
        self.df["Date"] = self.df.index.map(
            lambda i: self.start_date + timedelta(days=i)
        )

    def _get_employees(self):
        self.df.columns = self.df.columns.str.upper() if hasattr(self.df.columns, "str") else self.df.columns
        list_of_employees = []
        for column in self.df.columns:
            if isinstance(column, str) and column != "DATE":
                list_of_employees.append(column)
        self.list_of_employees = list_of_employees

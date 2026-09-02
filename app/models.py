from typing import List, Optional
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    amount: Optional[float] = None


class ConfidenceScores(BaseModel):
    vendor_name: float = Field(ge=0.0, le=1.0)
    invoice_date: float = Field(ge=0.0, le=1.0)
    total_amount: float = Field(ge=0.0, le=1.0)
    tax_amount: float = Field(ge=0.0, le=1.0)
    line_items: float = Field(ge=0.0, le=1.0)


class BillExtraction(BaseModel):
    is_bill_or_invoice: bool
    validation_reason: str
    vendor_name: Optional[str] = None
    invoice_date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    line_items: List[LineItem] = Field(default_factory=list)
    estimated_confidence: ConfidenceScores

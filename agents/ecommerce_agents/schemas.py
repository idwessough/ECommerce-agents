"""Pydantic models shared across the market analysis scaffold."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchScope(BaseModel):
    """Structured scope produced by the research scope agent."""

    canonical_product_name: str = Field(
        default="",
        description="Resolved product name.",
    )
    brand: str = Field(
        default="",
        description="Resolved product brand.",
    )
    category: str = Field(
        default="",
        description="Resolved product category.",
    )
    market: str = Field(
        default="",
        description="Market used for analysis, such as CA or US.",
    )
    requires_clarification: bool = Field(
        default=False,
        description="Whether the user request is ambiguous and needs follow-up.",
    )
    resolution_confidence: float = Field(
        default=0.0,
        description="Confidence score for product normalization.",
    )


class CompetitorCandidate(BaseModel):
    """A single competitor candidate discovered for the primary product."""

    brand: str
    model: str
    confidence: float


class PricingOffer(BaseModel):
    """A single observed market offer for a product."""

    seller: str
    price: float
    availability: str


class ProductPricing(BaseModel):
    """Pricing intelligence for a single product."""

    product: str
    currency: str
    msrp: float | None = None
    offers: list[PricingOffer] = Field(default_factory=list)
